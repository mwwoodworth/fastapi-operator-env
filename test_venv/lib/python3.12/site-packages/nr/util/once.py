
from __future__ import annotations

import typing as t

from nr.util.generic import T_co
from nr.util.types import Supplier


class Once(Supplier[T_co]):

  def __init__(self, supplier: Supplier[T_co]) -> None:
    self._supplier = supplier
    self._cached: bool = False
    self._value: T_co | None = None

  def __repr__(self) -> str:
    return f'Once({self._supplier!r})'

  def __bool__(self) -> bool:
    return self._cached

  def __call__(self) -> T_co:
    if not self._cached:
      self._value = self._supplier()
      self._cached = True
    return t.cast(T_co, self._value)

  def has_value(self) -> bool:
    return self._cached

  def get(self, force_refresh: bool = False) -> T_co:
    if force_refresh:
      self._cached = False
    return self()
