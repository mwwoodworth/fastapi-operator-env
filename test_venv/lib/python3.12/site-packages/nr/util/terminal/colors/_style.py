
from __future__ import annotations

import dataclasses
import re
import typing as t

from ._attribute import Attribute
from ._color import Color, parse_color


@dataclasses.dataclass
class Style:
  """ A style is a combination of foreground and background color, as well as a list of attributes. """

  RESET: t.ClassVar[Style]

  fg: Color | None = None
  bg: Color | None = None
  attrs: list[Attribute] | None = None

  def __init__(
    self,
    fg: Color | str | None = None,
    bg: Color | str | None = None,
    attrs: t.Sequence[Attribute | str] | str | None = None,
  ) -> None:
    """ The constructor allows you to specify all arguments also as strings. The foreground and background are parsed
    with #parse_color(). The *attrs* can be a comma-separated string. """

    if isinstance(fg, str):
      fg = parse_color(fg)
    if isinstance(bg, str):
      bg = parse_color(bg)
    if isinstance(attrs, str):
      attrs = [x.strip() for x in attrs.split(',') if x.strip()]
    self.fg = fg
    self.bg = bg
    if attrs is None:
      self.attrs = None
    else:
      self.attrs = []
      for attr in attrs:
        if isinstance(attr, str):
          self.attrs.append(Attribute[attr.upper()])
        else:
          self.attrs.append(attr)

  def to_escape_sequence(self) -> str:
    seq = []
    if self.fg:
      seq.append(self.fg.as_foreground())
    if self.bg:
      seq.append(self.bg.as_background())
    seq.extend(str(attr.value) for attr in self.attrs or ())
    return '\033[' + ';'.join(seq) + 'm'


Style.RESET = Style(attrs='reset')


class StyleManager:
  """ Allows you to register styles and format text using HTML-style tags. """

  TAG_EXPR = r'<([^>=]+)([^>]*)>(.*?)</\1>'

  def __init__(self) -> None:
    self._styles: dict[str, Style] = {}

  def add_style(
    self,
    name: str,
    fg: Color | str | None = None,
    bg: Color | str | None = None,
    attrs: list[Attribute | str] | str | None = None,
  ) -> None:
    self._styles[name] = Style(fg, bg, attrs)

  def parse_style(self, style_string: str, safe: bool = False) -> Style:
    """ Parses a style string that is valid inside an opening HTML-style tag accepted in strings by #format(). """

    parts = style_string.split(';')
    style: Style = Style()
    for part in parts:
      try:
        if part.startswith('fg='):
          style = Style(parse_color(part[3:]), style.bg, style.attrs)
        elif part.startswith('bg='):
          style = Style(style.fg, parse_color(part[3:]), style.attrs)
        elif part.startswith('attr='):
          style = Style(style.fg, style.bg, (style.attrs or []) + [Attribute[part[5:].upper()]])
        else:
          style = self._styles[part]
      except (ValueError, KeyError):
        if not safe:
          raise

    return style

  def format(self, text: str, safe: bool = False, repl: t.Callable[[str, str], str] | None = None) -> str:
    """ Formats text that contains HTML-style tags that represent styles in the style manager. In addition, special
    tags `<fg={color}>`, `<bg={color}>` or <attr={attrs}>` can be used to manually specify the exact styling of the
    text and the can be combined (such as `<bg=bright red;attr=underline>`). If *safe* is set to `True`, tags
    referencing styles that are unknown to the manager are ignored. """

    def _regex_sub(m: re.Match) -> str:
      style_string = m.group(1) + m.group(2)
      content = m.group(3)
      if repl is None:
        style = self.parse_style(style_string, safe)
        return style.to_escape_sequence() + content + Style.RESET.to_escape_sequence()
      else:
        return repl(style_string, content)

    upper_limit = 15
    prev_text = text
    for _ in range(upper_limit):
      text = re.sub(self.TAG_EXPR, _regex_sub, text, flags=re.S | re.M)
      if prev_text == text:
        break
      prev_text = text

    return prev_text

  @classmethod
  def strip_tags(cls, text: str) -> str:
    return cls().format(text, True, lambda _, s: s)
