
import threading
import typing as t


class AtomicCounter:
  """
  A thread-safe counter.
  """

  def __init__(self) -> None:
    self._value = 0
    self._lock = threading.Lock()
    self._cond = threading.Condition(self._lock)

  def get(self) -> int:
    """
    Get the current value of the counter.
    """

    with self._cond:
      return self._value

  def inc(self) -> None:
    """
    Increment the counter by one.
    """

    with self._cond:
      self._value += 1

  def dec(self) -> None:
    """
    Decrement the counter by one. Raises a #ValueError if attempting to decrement a value if zero.
    """

    with self._cond:
      if self._value == 0:
        raise ValueError('cannot decrement AtomicCounter below 0')
      self._value -= 1
      self._cond.notify_all()

  def join(self, timeout: t.Optional[float] = None) -> None:
    """
    Block until the counter reaches zero, or until the timeout expires.
    """

    with self._cond:
      self._cond.wait_for(lambda: self._value == 0, timeout)
