
from __future__ import annotations

import dataclasses
import sys


@dataclasses.dataclass
class Callsite:
  filename: str
  lineno: int
  code_name: str
  name: str | None


def get_callsite(stackdepth: int = 1) -> Callsite:
  """ Returns information on the callsite of the specified stackdepth. Defaults to 1 to point to the immediate
  stack frame above from where the function is called. The returned object contains information on the filename
  and line number. """

  frame = sys._getframe(stackdepth + 1)
  try:
    return Callsite(frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name, frame.f_globals.get('__name__'))
  finally:
    del frame
