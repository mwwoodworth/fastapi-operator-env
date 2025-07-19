
from __future__ import annotations

import dataclasses
import functools
import logging
import os
import typing as t
from importlib import import_module

from nr.util.process import Pidfile, replace_stdio, spawn_daemon

from . import AWSGILauncher, BaseAWSGIConfig

if t.TYPE_CHECKING:
  import flask  # type: ignore

logger = logging.getLogger(__name__)


def load_entrypoint(ep: str) -> t.Any:
  """
  Loads an entrypoint definition of the form `<module>:<member>`.
  """

  module_name, member_name = ep.split(':', 1)
  return getattr(import_module(module_name), member_name)



@dataclasses.dataclass
class FlaskRunner(AWSGILauncher, BaseAWSGIConfig):
  """
  Runs a #flask.Flask application using the Flask development server. This is not suitable
  for production, though very useful during development due to the built-in debugging
  capabilities.

  Note: Daemonizing the Flask runner is currently only available on systems that support
  #os.fork().
  """

  #: Enable the Flask server's debug capabilities.
  debug: bool = False

  #: Automatically defaults to `True` if #debug is enabled.
  use_reloader: bool | None = None

  #: Enable stdio redirects.
  redirect_stdio: bool = False

  def get_status(self) -> Pidfile.Status:
    """
    Returns the status of the application, i.e. whether it is currently running or not. This
    method is only relevant when the application was started in the background.
    """

    filename = self.files.pidfile
    if not filename:
      return Pidfile.Status.UNKNOWN
    return Pidfile(filename).get_status()

  def is_main(self) -> bool:
    """
    Checks whether this is the main process, which can be the reloader thread in case
    the #FlaskRunner is used.
    """

    if os.getenv('_FLASK_USE_RELOAER') == 'true':
      return not os.getenv('WERKZEUG_RUN_MAIN')

    return True

  def launch(self, entrypoint: str, factory: bool) -> None:
    import flask  # type: ignore[module]

    # Set up the environment.
    use_reloader = self.debug if self.use_reloader is None else self.use_reloader
    if use_reloader:
      os.environ['_FLASK_USE_RELOAER'] = 'true'
    if self.debug:
      os.environ['FLASK_DEBUG'] = 'true'

    # Load the Flask application.
    app = load_entrypoint(entrypoint)
    if factory:
      app = app()
    if not isinstance(app, flask.Flask):
      raise RuntimeError('entrypoint ({}) must be a Flask application.'.format(entrypoint))

    # Setup stdio redirects.
    if self.redirect_stdio:
      stdout, stderr = self._init_redirects(self.files)
    else:
      stdout, stderr = None, None

    if self.files.pidfile:
      os.makedirs(os.path.dirname(self.files.pidfile), exist_ok=True)

    if self.ssl:
      ssl_context = (self.ssl.cert, self.ssl.key)
    else:
      ssl_context = None

    run = functools.partial(
      self._run,
      app=app,
      stdout=stdout,
      stderr=stderr,
      pidfile=self.files.pidfile,
      daemon=self.daemonize,
      host=self.host,
      port=self.port,
      debug=self.debug,
      use_reloader=use_reloader,
      ssl_context=ssl_context)

    if self.is_main() and self.get_status() == Pidfile.Status.RUNNING:
      raise RuntimeError('Application is already running.')

    if self.daemonize:
      spawn_daemon(run)
    else:
      run()

  def _init_redirects(self, files: BaseAWSGIConfig.Files) -> tuple[t.TextIO | None, t.TextIO | None]:
    if files.stdout:
      os.makedirs(os.path.dirname(files.stdout), exist_ok=True)
      stdout = open(files.stdout, 'a+')
    else:
      stdout = None

    stderr: t.TextIO | None
    if files.stderr and files.stderr != files.stdout:
      os.makedirs(os.path.dirname(files.stderr), exist_ok=True)
      stderr = open(files.stderr, 'a+')
    elif files.stderr == files.stdout:
      stderr = stdout
    else:
      stderr = None

    return stdout, stderr

  def _run(
    self,
    app: 'flask.Flask',
    stdout: t.TextIO | None,
    stderr: t.TextIO | None,
    pidfile: str | None,
    daemon: bool,
    host: str,
    port: int,
    debug: bool,
    use_reloader: bool,
    ssl_context: tuple[str, str]
  ) -> None:
    """
    Internal function to actually invoke the Flask application after everything was prepared.
    """

    if stdout or stderr:
      replace_stdio(None, stdout, stderr)

    if pidfile:
      with open(pidfile, 'w') as fp:
        fp.write(str(os.getpid()))

    if daemon:
      logger.info('Process %s started.', os.getpid())

    try:
      app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=use_reloader,
        ssl_context=ssl_context,
      )
    finally:
      if (not use_reloader or os.getenv('WERKZEUG_RUN_MAIN') == 'true') and pidfile:
        try:
          logger.info('Removing pidfile "%s" from PID %s.', pidfile, os.getpid())
          os.remove(pidfile)
        except OSError as exc:
          logger.exception('Unable to remove "%s".', pidfile)
