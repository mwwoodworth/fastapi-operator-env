
from __future__ import annotations

import typing as t

from deprecated import deprecated

from nr.util.generic import T
from nr.util.iter import SequenceWalker as _SequenceWalker


@deprecated('use nr.util.iter.SequenceWalker instead')
class Scanner(_SequenceWalker[T]):

  @deprecated('use Scanner.safe_iter() instead')
  def ensure_advancing(self, strict_forward: bool = True) -> t.Iterator[T]:
    return self.safe_iter(strict_forward)
