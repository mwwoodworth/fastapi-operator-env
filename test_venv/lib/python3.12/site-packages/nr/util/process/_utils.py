
from __future__ import annotations

import errno
import grp
import os
import pwd
import signal
import sys
import time
import typing as t


def process_exists(pid: int) -> bool:
  """ Checks if the processed with the given *pid* exists. Returns #True if
  that is the case, #False otherwise. """

  if pid == 0:
    return False
  try:
    os.kill(pid, 0)
  except OSError as exc:
    if exc.errno == errno.ESRCH:
      return False
  return True


def process_terminate(pid: int, allow_kill: bool = True, timeout: int = 10) -> bool:
  """ Terminates the process with the given *pid*. First sends #signal.SIGINT,
  followed by #signal.SIGTERM after *timeout* seconds, followed by
  #signal.SIGKILL after *timeout* seconds if the process has not responded to
  the terminate signal.

  The fallback to kill can be disabled by setting *allow_kill* to False.
  Returns True if the process was successfully terminated or killed, or if
  the process did not exist in the first place. """

  def _wait(timeout):
    tstart = time.perf_counter()
    while (time.perf_counter() - tstart) < timeout:
      if not process_exists(pid):
        return True
      time.sleep(0.1)
    return False

  try:
    os.kill(pid, signal.SIGINT)
    if _wait(timeout):
      return True
    os.kill(pid, signal.SIGTERM)
    if _wait(timeout):
      return True
    if allow_kill:
      os.kill(pid, signal.SIGKILL)
      return _wait(timeout)
    return False
  except OSError as exc:
    if exc.errno == errno.ESRCH:
      return True
    raise


def getpwgrnam(user: str | None, group: str | None) -> tuple[str | None, int | None, int | None]:
  """ A combination of #pwd.getpwnam() and #pwd.getgrnam(), where *group*,
  if specified, overrides the group ID of the *user*. Returns a tuple of
  the user's home folder, the user ID and the group ID. """

  home, uid, gid = None, None, None
  if user:
    record = pwd.getpwnam(user)
    home, uid, gid = record.pw_dir, record.pw_uid, record.pw_gid
  if group:
    gid = grp.getgrnam(group).gr_gid
  return home, uid, gid


def replace_stdio(stdin: t.TextIO | None = None, stdout: t.TextIO | None = None, stderr: t.TextIO | None = None) -> None:
  """ Replaces the file handles of stdin/sdout/stderr, closing the original
  file descriptors if necessary. """

  if stdin:
    os.dup2(stdin.fileno(), sys.stdin.fileno())
  if stdout:
    os.dup2(stdout.fileno(), sys.stdout.fileno())
  if stderr:
    os.dup2(stderr.fileno(), sys.stderr.fileno())


def detach() -> None:
  """ Detaches the current process from the parent process. This function
  requires #os.setsid() and thus works only on Unix systems. """

  os.setsid()


def spawn_fork(func: t.Callable[[], t.Any], detach: bool = True) -> None:
  """ Spawns a single fork process and calls *func*. If *detach* is #True,
  the fork will be detached first (note that this process will still be killed
  by it's parent process if it doesn't exist gracefully).

  This is useful if *func* spawns another process, which will then behave like
  a daemon (as it will NOT be killed if the original process dies). """

  if not callable(func):
    raise TypeError('func is of type {} which is not callable'.format(
      type(func).__name__))

  pid = os.fork()
  if pid > 0:
    # Return to the original caller
    return
  if detach:
    os.setsid()
  func()
  os._exit(os.EX_OK)


def spawn_daemon(func: t.Callable[[], None]) -> None:
  """ Spawns a daemon process that runs *func*. This performs two forks to
  avoid the parent process killing the process that runs *func*.

  Note that this is only needed if you want to run a Python function as a
  daemon. If you were to spawn another process that should act as a daemon,
  you only need to fork once as the subprocess will then be the second "fork".
  """

  # TODO (@NiklasRosenstein): It would be great if the second fork could
  #   somehow report it's process ID to the original caller.

  if not callable(func):
    raise TypeError('func is of type {} which is not callable'.format(
      type(func).__name__))

  pid = os.fork()
  if pid > 0:
    # Return to the original caller.
    return
  os.setsid()
  pid = os.fork()
  if pid > 0:
    # Exit from second parent
    os._exit(os.EX_OK)
  func()
  os._exit(os.EX_OK)
