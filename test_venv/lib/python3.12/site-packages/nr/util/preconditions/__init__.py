
__author__ = 'Niklas Rosenstein <nrosenstein@palantir.com>'
__version__ = '0.0.4'

import typing as t

_T = t.TypeVar('_T')
_Message = t.Union[str, t.Callable[[], str]]
_Types = t.Union[type, t.Tuple[type, ...]]


def _get_message(message: _Message) -> str:
  if isinstance(message, str):
    return message
  else:
    return message()


def _repr_types(types: _Types) -> str:
  if isinstance(types, type):
    return types.__name__
  else:
    return '|'.join(t.__name__ for t in types)


def check_argument(value: bool, message: _Message) -> None:
  """
  Raise a #ValueError if the specified *value* is `False`. The specified *message* will be used as
  the message for the produced exception. The *message* may either be a string or an arg-less
  function that produces a string.
  """

  if not value:
    raise ValueError(_get_message(message))


def check_not_none(value: t.Optional[_T], message: _Message = None) -> _T:
  """
  Raises a #ValueError if *value* is `None`.
  """

  if value is None:
    raise ValueError(_get_message(message or 'cannot be None'))
  return value


@t.overload
def check_instance_of(value: t.Any, type_: t.Type[_T], message: _Message = None) -> _T: ...


@t.overload
def check_instance_of(value: t.Any, types: t.Tuple[t.Type, ...], message: _Message = None) -> t.Any: ...


def check_instance_of(value, types, message = None):
  """
  Raises a #TypeError if *value* is not an instance of the specified *types*. If no message is
  provided, it will be auto-generated for the given *types*.
  """

  if not isinstance(value, types):
    if message is None:
      message = f'expected {_repr_types(types)}, got {type(value).__name__} instead'
    raise TypeError(_get_message(message))
  return value


def check_subclass_of(cls: t.Type, types: _Types, message: _Message = None) -> t.Type:
  """
  Raises a #TypeError if *cls* is not a subclass of one of the specified *types*. If *cls* is not
  a type, a different #TypeError is raised that does not include the specified *message*.
  """

  check_instance_of(cls, type)
  if not issubclass(cls, types):
    if message is None:
      message = f'{cls.__name__} is not a subclass of {_repr_types(types)}'
    raise TypeError(_get_message(message))
  return cls
