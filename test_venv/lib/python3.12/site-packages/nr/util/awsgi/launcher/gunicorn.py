
import dataclasses
import os
import subprocess as sp

from . import AWSGILauncher, BaseAWSGIConfig


@dataclasses.dataclass
class GunicornRunner(AWSGILauncher, BaseAWSGIConfig):
  """
  Runs a WSGI application using [Gunicorn][0].

  [0]: https://gunicorn.org/
  """

  def launch(self, entrypoint: str, factory: bool) -> None:
    if factory:
      entrypoint += '()'
    command = ['gunicorn', entrypoint, '--bind', '{}:{}'.format(self.host, self.port)]
    if self.daemonize:
      command.append('--daemon')
    if self.files.pidfile:
      os.makedirs(os.path.dirname(self.files.pidfile), exist_ok=True)
      command += ['--pid', self.files.pidfile]
    if self.files.stdout:
      os.makedirs(os.path.dirname(self.files.stdout), exist_ok=True)
      command += ['--access-logfile', self.files.stdout]
    if self.files.stderr:
      os.makedirs(os.path.dirname(self.files.stderr), exist_ok=True)
      command += ['--error-logfile', self.files.stderr]
    if self.ssl:
      command += ['--certfile', self.ssl.cert, '--keyfile', self.ssl.key]
    if self.num_workers:
      command += ['--workers', str(self.num_workers)]
    command += self.additional_options
    sp.call(command)
