
import enum

from ._utils import process_exists, process_terminate


class Pidfile:

  class Status(enum.Enum):
    STOPPED = 0
    RUNNING = 1
    UNKNOWN = 2

  def __init__(self, filename: str) -> None:
    self.name = filename

  def set_pid(self, pid: int) -> None:
    """
    Writes the *pid* into the file.
    """

    with open(self.name) as fp:
      fp.write(str(pid))

  def get_pid(self) -> int:
    """
    Returns the PID saved in the file. May raise a #FileNotFounError if the file does not
    exist or a #ValueError if the file does not contain an integer.
    """

    with open(self.name) as fp:
      return int(fp.readline().strip())

  def get_status(self) -> Status:
    """
    Determines the #Status of a process.
    """

    try:
      pid = self.get_pid()
    except FileNotFoundError:
      return Pidfile.Status.STOPPED
    except ValueError:
      return Pidfile.Status.UNKNOWN
    if process_exists(pid):
      return Pidfile.Status.RUNNING
    return Pidfile.Status.STOPPED

  def stop(self) -> None:
    """
    Stops the process referenced by the PID file. If the file does not exist or the
    process is not alive, this is a no-op.
    """

    try:
      pid = self.get_pid()
    except (FileNotFoundError, ValueError):
      return
    process_terminate(pid)
