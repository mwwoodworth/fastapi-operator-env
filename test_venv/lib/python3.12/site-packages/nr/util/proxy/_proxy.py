
from __future__ import annotations

import typing as t

from nr.util.functional import Supplier
from nr.util.generic import T

from ._base import BaseProxy


class Proxy(BaseProxy[T]):
  """
  Wraps an object returned by a callable. Every time the proxy is accessed, the callable is invoked and the access is
  redirected to the proxied object.

  > __Note__: For some use cases, using a proxy can lead to problems when `isinstance()` or checks are used. For
  > example if you pass a proxy to a function that accepts an iterable, the instancecheck with
  > #collections.abc.Iterable will always return `True` as the #Proxy class implements the `__iter__()` method. If
  > you are stuck with this problem, use the #make_cls() function to create a new class excluding the `__iter__()`
  > method.
  """

  _func: Supplier[T]
  _lazy: bool
  _cache: t.Optional[T] = None

  def __init__(self, func: Supplier[T] | None = None, name: str | None = None, lazy: bool = False) -> None:
    """
    Create a new proxy object.

    # Arguments
    func (callable): The function that will be called to retrieve the object represented by the proxy when demanded.
      This will be called again and again for every operation performed on the proxy, unless #lazy is enabled. If no
      func is set, the proxy is unbound. The proxy can later be bound using the #bind() function.
    name (str): The name of the proxy. Can make debugging easier if the proxy is unbound.
    lazy (bool): Call the *func* function only once on first use, then cache the result.
    """

    object.__setattr__(self, "_func", func)
    object.__setattr__(self, "_lazy", lazy)
    object.__setattr__(self, "_cache", None)
    object.__setattr__(self, "__name__", name)

  def _set(self, value: T) -> None:
    object.__setattr__(self, "_func", None)
    object.__setattr__(self, "_lazy", True)
    object.__setattr__(self, "_cache", value)

  # proxy_base

  def _get_current_object(self) -> T:
    if self._lazy:
      if self._cache is None:
        if self._func is None:
          raise RuntimeError('unbound proxy')
        object.__setattr__(self, "_cache", self._func())
      return t.cast(T, self._cache)
    elif self._func is None:
      raise RuntimeError('unbound proxy')
    else:
      return self._func()

  def _is_bound(self) -> bool:
    return self._func is not None

  def _bind(self, func: t.Optional[Supplier[T]]) -> None:
    object.__setattr__(self, "_func", func)


def set_value(p: Proxy[T] | T, value: T) -> None:
  " Permanently override the value of a #proxy. This will turn the proxy to a lazy proxy if it is not already that. "

  t.cast(Proxy[T], p)._set(value)


def bind(p: Proxy[T] | T, func: Supplier[T] | None) -> None:
  """
  (Re-) bind the function for a proxy. The *func* will be called in the future when the current value of the
  proxy is required.
  """

  t.cast(Proxy[T], p)._bind(func)


def is_bound(p: t.Union[Proxy[T], T]) -> bool:
  return t.cast(Proxy[T], p)._is_bound()


def proxy(func: Supplier[T] | None = None, name: str | None = None, lazy: bool = False) -> T:
  """
  Create a new proxy from the given supplier. The function is typed to return an instance of the generic type
  *T*, but will in fact return a #Proxy object.
  """

  return t.cast(T, Proxy(func, name, lazy))

