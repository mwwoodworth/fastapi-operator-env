
import typing as t

import deprecated
import typing_extensions as te

from nr.util.generic import T_contra


@deprecated.deprecated('use `nr.util.types.Consumer` instead')
class Consumer(te.Protocol[T_contra]):

  def __call__(self, value: T_contra) -> t.Any:
    ...
