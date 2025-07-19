
import contextvars
import typing as t

from nr.util.generic import T

from ._stackable import StackableProxy


class ContextLocalProxy(StackableProxy[T]):
  """
  A proxy that stores a stack of objects in a #contextvars.ContextVar (for async programs).
  """

  _contextvar: contextvars.ContextVar
  _error_message: t.Optional[str]
  __name__: t.Optional[str]

  def __init__(self, name: t.Optional[str] = None, error_message: t.Optional[str] = None) -> None:
    """
    Create a new thread-local proxy. If an *error_message* is provided, it will be the
    message of the #RuntimeError that will be raised if the thread local is accessed
    without being initialized in the same thread first.
    """

    object.__setattr__(self, '_contextvar', contextvars.ContextVar('local'))
    object.__setattr__(self, '_error_message', error_message)
    object.__setattr__(self, '__name__', name)

  def _get_current_object(self) -> T:
    stack: t.List[T] = self._contextvar.get([])
    if not stack:
      message = self._error_message or 'contextlocal {name} is not initialized in this thread'
      raise RuntimeError(message.format(name=self.__name__ or '<unnamed>'))
    return stack[-1]

  def _empty(self) -> bool:
    stack: t.List[T] = self._contextvar.get([])
    return not stack

  def _push(self, value: T) -> None:
    assert value is not self, "cannot push contextlocal on itself"
    stack: t.Optional[t.List[T]] = self._contextvar.get(None)
    if stack is None:
      stack = []
      self._contextvar.set(stack)
    stack.append(value)

  def _pop(self) -> T:
    stack: t.List[T] = self._contextvar.get([])
    if not stack:
      name = self.__name__ or '<unnamed>'
      raise RuntimeError('there is no value to pop from contextlocal {}'.format(name))
    return stack.pop()


def contextlocal(name: t.Optional[str] = None, error_message: t.Optional[str] = None) -> t.Any:
  " Factory function to create a #ContextLocalProxy object, but typed to return any for convenience. "
  return ContextLocalProxy(name, error_message)
