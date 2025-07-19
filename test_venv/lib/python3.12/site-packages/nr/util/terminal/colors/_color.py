
import abc
import dataclasses
import enum
import re


class Color(abc.ABC):

  @abc.abstractmethod
  def as_foreground(self) -> str: ...

  @abc.abstractmethod
  def as_background(self) -> str: ...


class SgrColorName(enum.Enum):
  BLACK = 0
  RED = 1
  GREEN = 2
  YELLOW = 3
  BLUE = 4
  MAGENTA = 5
  CYAN = 6
  WHITE = 7
  GRAY = 8
  DEFAULT = 9


@dataclasses.dataclass
class SgrColor(Color):
  """ Represents a color from the SGR space (see #SgrColorName). """

  name: SgrColorName
  bright: bool

  def __init__(self, name: SgrColorName, bright: bool = False) -> None:
    if isinstance(name, str):
      name = SgrColorName[name.upper()]
    self.name = name
    self.bright = bright

  def as_foreground(self) -> str:
    return str((90 if self.bright else 30) + self.name.value)

  def as_background(self) -> str:
    return str((100 if self.bright else 40) + self.name.value)


@dataclasses.dataclass
class LutColor(Color):
  """ Represents a LUT color, which is one of 216 colors. """

  index: int

  def as_foreground(self) -> str:
    return '38;5;' + str(self.index)

  def as_background(self) -> str:
    return '48;5;' + str(self.index)

  @classmethod
  def from_rgb(cls, r: int, g: int, b: int) -> 'LutColor':
    """
    Given RGB values in the range of [0..5], returns a #LutColor pointing
    to the color index that resembles the specified color coordinates.
    """

    def _check_range(name, value):
      if not (0 <= value < 6):
        raise ValueError('bad value for parameter "{}": {} ∉ [0..5]'.format(name, value))

    _check_range('r', r)
    _check_range('g', g)
    _check_range('b', b)

    return cls((16 + 36 * r) + (6 * g) + b)


class TrueColor(Color):
  """ Represents a true color comprised of three color components. """

  r: int
  g: int
  b: int

  def as_foreground(self) -> str:
    return '38;2;{};{};{}'.format(self.r, self.g, self.b)

  def as_background(self) -> str:
    return '48;2;{};{};{}'.format(self.r, self.g, self.b)


def parse_color(color_string: str) -> Color:
  """ Parses a color string of one of the following formats and returns a corresponding #SgrColor, #LutColor or
  #TrueColor.

  * `<color_name>`, `BRIGHT_<color_name>`: #SgrColor (case insensitive, underline optional)
  * `%rgb`, `$xxx`: #LutColor
  * `#cef`, `#cceeff`: #TrueColor
  """

  if color_string.startswith('%') and len(color_string) == 4:
    try:
      r, g, b = map(int, color_string[1:])
    except ValueError:
      pass
    else:
      if r < 6 and g < 6 and b < 6:
        return LutColor.from_rgb(r, g, b)

  elif color_string.startswith('$') and len(color_string) <= 4:
    try:
      index = int(color_string[1:])
    except ValueError:
      pass
    else:
      if index >= 0 and index < 256:
        return LutColor(index)

  elif color_string.startswith('#') and len(color_string) in (4, 7):
    parts = re.findall('.' if len(color_string) == 4 else '..', color_string[1:])
    if len(color_string) == 4:
      parts = [x*2 for x in parts]
    try:
      parts = [int(x, 16) for x in parts]
    except ValueError:
      pass
    else:
      return TrueColor(*parts)

  else:
    color_string = color_string.upper()
    bright = color_string.startswith('BRIGHT_') or color_string.startswith('BRIGHT ')
    if bright:
      color_string = color_string[7:]
    if hasattr(SgrColorName, color_string):
      return SgrColor(SgrColorName[color_string], bright)

  raise ValueError('unrecognizable color string: {!r}'.format(color_string))
