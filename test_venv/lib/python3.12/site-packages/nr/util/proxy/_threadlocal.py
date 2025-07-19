
import threading
import typing as t

from nr.util.generic import T

from ._stackable import StackableProxy


class ThreadLocalProxy(StackableProxy[T]):
  """
  A proxy that contains a thread-local stack of objects.
  """

  _local: threading.local
  _error_message: t.Optional[str]
  __name__: t.Optional[str]

  def __init__(self, name: t.Optional[str] = None, error_message: t.Optional[str] = None) -> None:
    """
    Create a new thread-local proxy. If an *error_message* is provided, it will be the
    message of the #RuntimeError that will be raised if the thread local is accessed
    without being initialized in the same thread first.
    """

    object.__setattr__(self, '_local', threading.local())
    object.__setattr__(self, '_error_message', error_message)
    object.__setattr__(self, '__name__', name)

  def _get_current_object(self) -> T:
    stack: t.List[T] = getattr(self._local, 'stack', [])
    if not stack:
      message = self._error_message or 'threadlocal {name} is not initialized in this thread'
      raise RuntimeError(message.format(name=self.__name__ or '<unnamed>'))
    return stack[-1]

  def _empty(self) -> bool:
    stack: t.List[T] = getattr(self._local, 'stack', [])
    return not stack

  def _push(self, value: T) -> None:
    assert value is not self, "cannot push threadlocal on itself"
    stack: t.Optional[t.List[T]] = getattr(self._local, 'stack', None)
    if stack is None:
      stack = []
      self._local.stack = stack
    stack.append(value)

  def _pop(self) -> T:
    stack: t.List[T] = getattr(self._local, 'stack', [])
    if not stack:
      name = self.__name__ or '<unnamed>'
      raise RuntimeError('there is no value to pop from threadlocal {}'.format(name))
    return stack.pop()


def threadlocal(name: t.Optional[str] = None, error_message: t.Optional[str] = None) -> t.Any:
  " Factory function to create a #ThreadLocalProxy object, but typed to return any for convenience. "
  return ThreadLocalProxy(name, error_message)
