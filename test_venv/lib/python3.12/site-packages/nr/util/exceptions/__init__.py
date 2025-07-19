
""" Utils for implement and dealing with exceptions. """

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
  from nr.util.generic import T


def safe_str(func: t.Callable[[T], str]) -> t.Callable[[T], str]:
  """ Decorator for a #__str__() method of an #Exception subclass that catches an exception that occurs in the
  string formatting function, logs it and returns the message of the occurred exception instead. """

  import functools
  import logging

  @functools.wraps(func)
  def wrapper(self) -> str:
    try:
      return func(self)
    except Exception as exc:
      type_name = type(self).__module__ + '.' + type(self).__name__
      logger = logging.getLogger(type_name)
      logger.exception('Unhandled exception in %s.__str__()', type_name)
      return str(exc)

  return wrapper
