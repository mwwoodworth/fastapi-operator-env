
import copy
import typing as t

from nr.util.generic import T


class BaseProxy(t.Generic[T]):
  " Base class for proxy objects, which implements all method delegation to #_get_current_object(). "

  __is_proxy__ = True

  def _get_current_object(self) -> t.Any:
    raise NotImplementedError

  # forward special function calls and attribute access

  @property
  def __dict__(self):
    try:
      return self._get_current_object().__dict__
    except RuntimeError:
      raise AttributeError("__dict__")

  def __repr__(self) -> str:
    try:
      obj = self._get_current_object()
    except RuntimeError:
      return "<unresolvable {}.{} ({})>".format(
        type(self).__module__,
        type(self).__name__,
        get_name(self) or '<unnamed>')  # type: ignore
    return repr(obj)

  def __bool__(self):
    try:
      return bool(self._get_current_object())
    except RuntimeError:
      return False

  def __dir__(self):
    try:
      return dir(self._get_current_object())
    except RuntimeError:
      return []

  def __getattr__(self, name):
    if name == '__members__':
      return dir(self._get_current_object())
    return getattr(self._get_current_object(), name)

  def __setitem__(self, key, value):
    self._get_current_object()[key] = value

  def __delitem__(self, key):
    del self._get_current_object()[key]

  def __call__(self, *a, **kw):
    return self._get_current_object()(*a, **kw)

  def __setattr__(self, name, value):
    if name == '__orig_class__':
      # Support for generic instantiation of the proxy type.
      object.__setattr__(self, name, value)
    else:
      setattr(self._get_current_object(), name, value)

  __delattr__ = lambda x, n: delattr(x._get_current_object(), n)  # type: ignore
  __str__ = lambda x: str(x._get_current_object())  # type: ignore
  __lt__ = lambda x, o: x._get_current_object() < o
  __le__ = lambda x, o: x._get_current_object() <= o
  __eq__ = lambda x, o: x._get_current_object() == o  # type: ignore
  __ne__ = lambda x, o: x._get_current_object() != o  # type: ignore
  __gt__ = lambda x, o: x._get_current_object() > o
  __ge__ = lambda x, o: x._get_current_object() >= o
  __hash__ = lambda x: hash(x._get_current_object())  # type: ignore
  __len__ = lambda x: len(x._get_current_object())
  __getitem__ = lambda x, i: x._get_current_object()[i]
  __iter__ = lambda x: iter(x._get_current_object())
  __contains__ = lambda x, i: i in x._get_current_object()
  __add__ = lambda x, o: x._get_current_object() + o
  __sub__ = lambda x, o: x._get_current_object() - o
  __mul__ = lambda x, o: x._get_current_object() * o
  __floordiv__ = lambda x, o: x._get_current_object() // o
  __mod__ = lambda x, o: x._get_current_object() % o
  __divmod__ = lambda x, o: x._get_current_object().__divmod__(o)
  __pow__ = lambda x, o: x._get_current_object() ** o
  __lshift__ = lambda x, o: x._get_current_object() << o
  __rshift__ = lambda x, o: x._get_current_object() >> o
  __and__ = lambda x, o: x._get_current_object() & o
  __xor__ = lambda x, o: x._get_current_object() ^ o
  __or__ = lambda x, o: x._get_current_object() | o
  __div__ = lambda x, o: x._get_current_object().__div__(o)
  __truediv__ = lambda x, o: x._get_current_object().__truediv__(o)
  __neg__ = lambda x: -(x._get_current_object())
  __pos__ = lambda x: +(x._get_current_object())
  __abs__ = lambda x: abs(x._get_current_object())
  __invert__ = lambda x: ~(x._get_current_object())
  __complex__ = lambda x: complex(x._get_current_object())
  __int__ = lambda x: int(x._get_current_object())
  __float__ = lambda x: float(x._get_current_object())
  __oct__ = lambda x: oct(x._get_current_object())
  __hex__ = lambda x: hex(x._get_current_object())
  __index__ = lambda x: x._get_current_object().__index__()
  __coerce__ = lambda x, o: x._get_current_object().__coerce__(x, o)
  __enter__ = lambda x: x._get_current_object().__enter__()
  __exit__ = lambda x, *a, **kw: x._get_current_object().__exit__(*a, **kw)
  __radd__ = lambda x, o: o + x._get_current_object()
  __rsub__ = lambda x, o: o - x._get_current_object()
  __rmul__ = lambda x, o: o * x._get_current_object()
  __rdiv__ = lambda x, o: o / x._get_current_object()
  __rtruediv__ = __rdiv__
  __rfloordiv__ = lambda x, o: o // x._get_current_object()
  __rmod__ = lambda x, o: o % x._get_current_object()
  __rdivmod__ = lambda x, o: x._get_current_object().__rdivmod__(o)
  __copy__ = lambda x: copy.copy(x._get_current_object())
  __deepcopy__ = lambda x, memo: copy.deepcopy(x._get_current_object(), memo)
  __class__ = property(lambda x: type(x._get_current_object()))  # type: ignore


def get(p: t.Union[BaseProxy[T], T]) -> T:
  " Dereference the proxy to get it's current value. "
  return t.cast(BaseProxy[T], p)._get_current_object()


def get_name(p: t.Union[BaseProxy[T], T]) -> t.Optional[str]:
  " Returns the name of a proxy object, if one was specified on construction. "
  try:
    return t.cast(str, object.__getattribute__(p, '__name__'))
  except AttributeError:
    return None
