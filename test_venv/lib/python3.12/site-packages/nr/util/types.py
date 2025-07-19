
from __future__ import annotations

import abc
import typing as t

import typing_extensions as te

from nr.util.generic import T, T_co, T_contra

if t.TYPE_CHECKING:
  from nr.util.once import Once


T_Comparable = t.TypeVar('T_Comparable', bound='Comparable')
class Comparable(te.Protocol):
  def __lt__(self, other: t.Any) -> bool: ...


T_Consumer = t.TypeVar('T_Consumer', bound='Consumer')
class Consumer(abc.ABC, t.Generic[T]):

  @abc.abstractmethod
  def __call__(self, value: T) -> t.Any: ...

  @staticmethod
  def of(func: t.Callable[[T], t.Any]) -> Consumer[T]:
    return t.cast(Consumer[T], func)


T_Predicate = t.TypeVar('T_Predicate', bound='Predicate')
class Predicate(abc.ABC, t.Generic[T_contra]):

  @abc.abstractmethod
  def __call__(self, obj: T_contra) -> bool: ...

  @staticmethod
  def of(func: t.Callable[[T_contra], bool]) -> Predicate[T_contra]:
    return t.cast(Predicate[T_contra], func)


T_Supplier = t.TypeVar('T_Supplier', bound='Supplier')
class Supplier(abc.ABC, t.Generic[T_co]):

  @abc.abstractmethod
  def __call__(self) -> T_co: ...

  @staticmethod
  def of(func: t.Callable[[], T_co]) -> Supplier[T_co]:
    return t.cast(Supplier[T_co], func)

  @staticmethod
  def once(func: t.Callable[[], T_co]) -> Once[T_co]:
    from nr.util.once import Once
    return Once(Supplier.of(func))
