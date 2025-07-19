
"""
Provides the #Scanner class which is convenient for scanning through items of a sequence; such as characters
in a text.
"""

from __future__ import annotations

import enum
import re
import typing as t

import typing_extensions as te


class Cursor(t.NamedTuple):
  offset: int
  line: int
  column: int

  def get_line_begin(self) -> Cursor:
    """ Returns a cursor pointing to the beginning of the current line. """
    return Cursor(self.offset - self.column + 1, self.line, 1)


class Seek(enum.Enum):
  SET = enum.auto()
  CUR = enum.auto()
  END = enum.auto()


class Scanner:
  """
  A convenient class for scanning through items of a sequence; such as characters in a text.
  """

  def __init__(self, text: str) -> None:
    self.text = text
    self._index = 0
    self._lineno = 1
    self._colno = 1

  def __repr__(self) -> str:
    return f'<Scanner at {self._lineno}:{self._colno}>'

  def __bool__(self) -> bool:
    return self._index < len(self.text)

  def __setattr__(self, key: str, value: t.Any) -> None:
    if key == '_index':
      min_value = 0
    elif key in ('_lineno', '_colno'):
      min_value = 1
    else:
      min_value = None
    if min_value is not None and value < min_value:
      raise RuntimeError(f'{key} cannot be set below {min_value}')
    object.__setattr__(self, key, value)

  @property
  def pos(self) -> Cursor:
    return Cursor(self._index, self._lineno, self._colno)

  @pos.setter
  def pos(self, cursor: Cursor) -> None:
    """ Moves the scanner back (or forward) to the specified cursor location. """

    if not isinstance(cursor, Cursor):
      raise TypeError(f'expected Cursor object {type(cursor).__name__}')
    self._index, self._lineno, self._colno = cursor

  @property
  def char(self) -> str:
    """ Returns the current character. Returns an empty string at the end of the text. """

    if self._index >= 0 and self._index < len(self.text):
      return self.text[self._index]
    else:
      return type(self.text)()

  def seek(self, offset: int, mode: te.Literal['set', 'cur', 'end'] | Seek = Seek.SET) -> None:
    """
    Moves the cursor of the Scanner to or by *offset* depending on the *mode*. The method is
    similar to a file's `seek()` method, but ensures that the line and column counts are tracked
    correctly.
    """

    if isinstance(mode, str):
      mode = Seek[mode.upper()]
    if mode not in Seek:
      raise ValueError(f'invalid mode: {mode!r}')

    # Translate the other modes into the 'set' mode.
    if mode == Seek.END:
      offset = len(self.text) + offset
    elif mode == Seek.CUR:
      offset = self._index + offset

    offset = max(0, min(len(self.text), offset))

    # Start counting from scratch.
    current_offset = 0
    colno = 1
    lineno = 1
    while current_offset != offset:
      newline_idx = self.text.find('\n', current_offset)
      if newline_idx >= offset or newline_idx < 0:
        left_newline_idx = self.text.rfind('\n', None, newline_idx if newline_idx >= 0 else len(self.text))
        colno = offset + 1 if left_newline_idx < 0 else offset - left_newline_idx
        current_offset = offset
        break
      else:
        current_offset = newline_idx + 1
        lineno += 1

    self._index, self._lineno, self._colno = current_offset, lineno, colno

  def next(self) -> str:
    """ Move on to the next character in the text. """

    if self._index >= len(self.text):
      return ''

    char = self.char
    if char == '\n':
      self._lineno += 1
      self._colno = 1
    else:
      self._colno += 1
    self._index += 1
    return self.char

  def readline(self) -> str:
    """ Reads a full line from the scanner and returns it. """

    start = end = self._index
    while end < len(self.text):
      if self.text[end] == '\n':
        end += 1
        break
      end += 1
    result = self.text[start:end]
    self._index = end
    if result.endswith('\n'):
      self._colno = 0
      self._lineno += 1
    else:
      self._colno += end - start
    return result

  def match(self, regex: t.Union[str, 're.Pattern'], flags: int = 0, *,
      _search: bool = False) -> t.Optional[t.Match[str]]:
    """
    Matches the *regex* from the current character of the *scanner* and returns the result. The
    scanners column and line numbers are updated respectively.
    """

    if isinstance(regex, str):
      regex = re.compile(regex, flags)
    match = (regex.search if _search else regex.match)(self.text, self._index)
    if not match:
      return None
    start, end = match.start(), match.end()
    if not _search:
      assert start == self._index, (start, self._index)
    else:
      start = self._index
    lines = self.text.count('\n', start, end)
    self._index = end
    if lines:
      self._colno = end - self.text.rfind('\n', start, end)
      self._lineno += lines
    else:
      self._colno += end - start
    return match

  def search(self, regex: t.Union[str, 're.Pattern'], flags: int = 0) -> t.Optional['re.Match']:
    """
    Performs a regex search from the current position of the scanner. Note that searching in the
    scanner will potentially have you skip characters without consuming them.
    """

    return self.match(regex, flags, _search=True)

  def getmatch(self, regex: t.Union[str, 're.Pattern'], group: t.Union[int,str] = 0,
      flags: int = 0) -> t.Optional[str]:
    """
    The same as #Scanner.match(), but returns the captured group rather than
    the regex match object, or None if the pattern didn't match.
    """

    match = self.match(regex, flags)
    if match:
      return match.group(group)
    return None

  def getline(self, cursor: Cursor) -> str:
    """ Returns the contents of the current line marked by the specified cursor location. """

    start = cursor.offset - cursor.column
    end = self.text.find('\n', start)
    if end < 0:
      end = len(self.text)
    return self.text[start:end]
