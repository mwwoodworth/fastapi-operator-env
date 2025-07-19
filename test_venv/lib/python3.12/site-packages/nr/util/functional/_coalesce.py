
import typing as t

from nr.util.generic import T


@t.overload
def coalesce(value: t.Optional[T], fallback: T) -> T: ...

@t.overload
def coalesce(value: t.Optional[T], *values: t.Optional[T]) -> t.Optional[T]: ...

@t.overload
def coalesce(value: t.Optional[T], *values: t.Optional[T], fallback: T) -> T: ...

def coalesce(value: t.Optional[T], *values: t.Optional[T], fallback: t.Optional[T] = None) -> t.Optional[T]:
  """
  Returns the first value that is not `None`. If a not-None fallback is specified, the function is guaranteed
  to return a not-Non value.
  """

  if value is not None:
    return value

  value = next((x for x in values if x is not None), None)
  if value is not None:
    return value

  return fallback
