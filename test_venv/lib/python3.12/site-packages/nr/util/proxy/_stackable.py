
import typing as t

from nr.util.generic import T

from ._base import BaseProxy


class StackableProxy(BaseProxy[T]):
  " Base class for proxies that can act as a stack and delegate to the item at the top of the stack. "

  def _empty(self) -> bool:
    raise NotImplementedError

  def _push(self, value: T) -> None:
    raise NotImplementedError

  def _pop(self) -> T:
    raise NotImplementedError


def empty(p: t.Union[StackableProxy[T], T]) -> bool:
  " Returns `True` if the stackable proxy is empty. "
  return t.cast(StackableProxy[T], p)._empty()


def push(p: t.Union[StackableProxy[T], T], value: T) -> None:
  " Push a value on a stackable proxy. "
  t.cast(StackableProxy[T], p)._push(value)


def pop(p: t.Union[StackableProxy[T], T]) -> T:
  " Pop a value from a stackable proxy. "
  return t.cast(StackableProxy[T], p)._pop()
