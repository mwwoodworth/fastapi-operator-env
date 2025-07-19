
import typing as t

if t.TYPE_CHECKING:
  from .._scanner import Scanner

T = t.TypeVar('T')
U = t.TypeVar('U')


class TokenExtractor(t.Generic[T]):
  """ Interface for token extraction. """

  def get_token(self, scanner: 'Scanner') -> t.Optional[T]:
    """ Extract a token value from the current position of the scanner. """

    raise NotImplementedError(f'{type(self).__name__}.get_token() is not implemented')

  @staticmethod
  def of(impl: t.Callable[['Scanner'], t.Optional[T]]) -> 'TokenExtractor[T]':
    return _LambdaTokenExtractor(impl)

  def map(self, func: t.Callable[[T], U]) -> 'TokenExtractor[U]':
    return _MappedTokenExtractor(func, self)


class _LambdaTokenExtractor(TokenExtractor[T]):

  def __init__(self, impl: t.Callable[['Scanner'], t.Optional[T]]) -> None:
    self._impl = impl

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self._impl})'

  def get_token(self, scanner: 'Scanner') -> t.Optional[T]:
    return self._impl(scanner)


class _MappedTokenExtractor(TokenExtractor[U]):

  def __init__(self, func: t.Callable[[T], U], inner: TokenExtractor[T]) -> None:
    self._func = func
    self._inner = inner

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self._func}, {self._inner})'

  def get_token(self, scanner: 'Scanner') -> t.Optional[U]:
    value = self._inner.get_token(scanner)
    if value is not None:
      return self._func(value)
    return None
