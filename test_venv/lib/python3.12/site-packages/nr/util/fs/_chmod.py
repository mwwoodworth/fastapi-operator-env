
import functools
import operator
import os
import stat
import typing as t
from pathlib import Path


def flags(flags: int, modstring: str) -> int:
  """ Modifies the stat flags according to *modstring*, mirroring the syntax for POSIX `chmod`. """

  mapping = {
    'r': (stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH),
    'w': (stat.S_IWUSR, stat.S_IWGRP, stat.S_IWOTH),
    'x': (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH)
  }

  target, direction = 'a', None
  for c in modstring:
    if c in '+-':
      direction = c
      continue
    if c in 'ugoa':
      target = c
      direction = None  # Need a - or + after group specifier.
      continue
    if c in 'rwx' and direction and direction in '+-':
      if target == 'a':
        mask = functools.reduce(operator.or_, mapping[c])
      else:
        mask = mapping[c]['ugo'.index(target)]
      if direction == '-':
        flags &= ~mask
      else:
        flags |= mask
      continue
    raise ValueError('invalid chmod: {!r}'.format(modstring))

  return flags


def repr(flags: int) -> str:
  """ Returns a string representation of the access flags *flags*. """

  template = 'rwxrwxrwx'
  order = (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
           stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
           stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)
  return ''.join(template[i] if flags&x else '-' for i, x in enumerate(order))


def update(path: t.Union[str, Path], modstring: str) -> None:
  """ Updates the mode of the *path* in a `chmod` like fashion. """

  os.chmod(path, flags(os.stat(path).st_mode, modstring))
