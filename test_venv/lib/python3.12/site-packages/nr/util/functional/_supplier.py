
from __future__ import annotations

import typing as t

import deprecated
import typing_extensions as te

from nr.util.generic import T_co, U


@deprecated.deprecated('will be removed in a future version')
def supplier_get(value: Supplier[T_co] | U) -> T_co | U:
  """ A helper method to invoke a supplier, if *value* is a supplier, or return the value directory. This is
  useful in particular for patterns where a static value as well as a supplier is a valid value for the variable.
  Note that the type *U* must not be callable, otherwise it is recognized as a supplier.

  __Example__

    site_name: Supplier[str | None] | str | None = ...
    value = supplier_get(site_name)
  """

  if callable(value):
    return value()
  return value


@deprecated.deprecated('use `nr.util.types.Supplier` instead')
class Supplier(te.Protocol[T_co]):

  def __call__(self) -> T_co:
    ...


@deprecated.deprecated('will be removed in a future version')
class ContextSupplier(Supplier[t.ContextManager[T_co]]):
  ...
