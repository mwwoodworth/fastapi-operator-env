
from __future__ import annotations

import sys
from pathlib import Path


def is_relative_to(a: Path | str, b: Path | str) -> bool:
  """ Returns `True` if path *a* is relative to path *b*. A backfill for #Path.is_relative_to() for Python versions
  older than 3.9. """

  if sys.version_info < (3, 9):
    try:
      Path(a).relative_to(b)
    except ValueError:
      return False
    return True
  else:
    return Path(a).is_relative_to(b)
