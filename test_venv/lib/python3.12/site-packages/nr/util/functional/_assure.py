
from __future__ import annotations

import deprecated

from nr.util.generic import T
from nr.util.preconditions import _get_message, _Message, check_not_none


@deprecated.deprecated('use `nr.util.preconditions.check_not_none()` instead')
def assure(v: T | None, msg: _Message | None = None) -> T:
  """ Assures that *v* is not `None` and returns it. If the value is in fact `None`, a {@link ValueError} will
  be raised raised. """

  if v is None:
    raise ValueError(_get_message(msg) if msg else 'expected value to not be None')
  return v
