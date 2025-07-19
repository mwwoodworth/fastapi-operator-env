
import typing as t

import deprecated
import typing_extensions as te

from nr.util.generic import T_contra


@deprecated.deprecated('use `nr.util.types.Predicate` instead')
class Predicate(te.Protocol[T_contra]):

  def __call__(self, obj: T_contra) -> bool:
    ...
