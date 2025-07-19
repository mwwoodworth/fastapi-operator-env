
import enum
import logging
import typing as t
from dataclasses import dataclass, field

from .._scanner import Cursor, Scanner
from .ruleset import Rule, RuleConfigSet, RuleSet

T = t.TypeVar('T')
U = t.TypeVar('U')
V = t.TypeVar('V')
R = t.TypeVar('R')


class Debug(enum.IntEnum):
  """ Flags that enable/disable various debug logs in the tokeninzer. """

  #: Log the final computed values for the "select" and "expect" arguments in the
  #: #Tokenizer.next() function.
  NEXT_ARGS = (1 << 0)

  #: Log the extracted token in #Tokenizer.next().
  EXTRACT = (1 << 1)

  #: Log when #Tokenizer.pos is set.
  UPDATE_POS = (1 << 2)

  NONE = 0
  ALL = (NEXT_ARGS | EXTRACT | UPDATE_POS)


@dataclass
class Token(t.Generic[T, U]):
  """
  Represents a token extracted by the tokenizer. When the end of the text is reached and no more
  tokens can be extracted, the *type* and *value* will be set to what is defined in the #RuleSet
  to be used as the sentinel.
  """

  type: T
  value: U
  pos: 'Cursor'
  eof: bool = field(repr=False)

  def __bool__(self) -> bool:
    return not self.eof

  @property
  def tv(self) -> t.Tuple[T, U]:
    return (self.type, self.value)


class ProxyToken(t.Generic[T, U]):
  """ Always represents the current token of the tokenizer. """

  def __init__(self,
    tokenizer: 'Tokenizer[T, U]',
    transformer: t.Optional[t.Callable[[Token[T, U]], Token[T, U]]] = None,
  ) -> None:
    self.tokenizer = tokenizer
    self.transformer = transformer
    self._transformed_token: t.Optional[t.Tuple[Token[T, U], Token[T, U]]] = None

  def __repr__(self) -> str:
    return f'TokenProxy({self._token!r})'

  def __bool__(self) -> bool:
    return bool(self._token)

  def __call__(self) -> Token[T, U]:
    return self._token

  @property
  def _token(self) -> Token[T, U]:
    if self.transformer is None:
      return self.tokenizer.current
    if self._transformed_token is not None and \
        self._transformed_token[0] is self.tokenizer.current:
      return self._transformed_token[1]
    self._transformed_token = (self.tokenizer.current, self.transformer(self.tokenizer.current))
    return self._transformed_token[1]

  @property
  def type(self) -> T:
    return self._token.type

  @property
  def value(self) -> U:
    return self._token.value

  @property
  def pos(self) -> Cursor:
    return self._token.pos

  @property
  def eof(self) -> bool:
    return self._token.eof

  @property
  def tv(self) -> t.Tuple[T, U]:
    return self._token.tv

  def next(self) -> None:
    self.tokenizer.next()

  def save(self) -> 'TokenizerState':
    return self.tokenizer.state

  def load(self, pos: 'TokenizerState') -> None:
    self.tokenizer.state = pos

  def set_ignored(self, token_types: t.Union[T, t.Collection[T]], ignored: bool = True) -> t.ContextManager[None]:
    return self.tokenizer.ignored.set(token_types, ignored)

  def set_skipped(self, token_types: t.Union[T, t.Collection[T]], skipped: bool = True) -> t.ContextManager[None]:
    return self.tokenizer.skipped.set(token_types, skipped)


@dataclass
class TokenizerState(t.Generic[T, U]):
  """ A checkpoint that can be used to restore the tokenizer to a previous state. """

  cursor: 'Cursor'
  token: t.Optional[Token[T, U]]
  skipped: RuleConfigSet[T, U, bool]
  ignored: RuleConfigSet[T, U, bool]
  skip_rule_once: t.Optional[Rule[T, U]]


class TokenizationError(Exception):
  """ Raised when the text cannot be tokenized. """


class UnexpectedTokenError(Exception):
  """ Raised when the text could only be tokenized into an unexpected token. """


class Tokenizer(t.Generic[T, U]):
  """ Splits text from a #Scanner into #Token#s via rules provided by a #Lexer. """

  log = logging.getLogger(__module__ + '.' + __qualname__)  # type: ignore

  #: The rule set that is used for tokenization.
  rules: 'RuleSet'

  #: The scanner that provides the text to be tokenized.
  scanner: 'Scanner'

  #: This config set defines the token types that are skipped when encountered (that means
  #: they are not returned by #next() or included when iterating over the tokenizer).
  skipped: RuleConfigSet[T, U, bool]

  #: This config set defines the token types that are ignored by the lexer (that means that
  #: are treated as if they would not exist in the rule set).
  ignored: RuleConfigSet[T, U, bool]

  def __init__(self, rules: 'RuleSet[T, U]', scanner: t.Union[str, 'Scanner'], debug: Debug = Debug.NONE) -> None:
    if isinstance(scanner, str):
      scanner = Scanner(scanner)
    self.rules = rules
    self.scanner = scanner
    self._current: t.Optional[Token[T, U]] = None
    self.skipped = RuleConfigSet(rules)
    self.ignored = RuleConfigSet(rules)
    self.debug = debug

    # Keep track if a zero-length token was extracted via a rule. That rule cannot trigger again
    # from the same position of the tokenizer.
    self._skip_rule_once: t.Optional[Rule[T, U]] = None

  def __bool__(self) -> bool:
    return bool(self.scanner) or bool(self._current)

  def __iter__(self) -> t.Iterator[Token[T, U]]:
    token = self.current
    while token:
      yield token
      token = self.next()

  @property
  def state(self) -> TokenizerState[T, U]:
    """ The position of the tokenizer. Can be set to go back to a previously stored position. """

    return TokenizerState(self.scanner.pos, self._current, self.skipped.copy(),
      self.ignored.copy(), self._skip_rule_once)

  @state.setter
  def state(self, state: TokenizerState[T, U]) -> None:
    if self.debug & Debug.UPDATE_POS:
      self.log.debug('Update Tokenizer.pos (pos=%r)', state)
    self.scanner.pos = state.cursor
    self._current = state.token
    self.skipped = state.skipped
    self.ignored = state.ignored
    self._skip_rule_once = state.skip_rule_once

  @property
  def current(self) -> Token[T, U]:
    """
    Returns the token that was last extracted in the #next() method. Raises an #EOF exception if
    the scanner has reached the end of the text. Raises a #RuntimeError if #next() has not been
    called successfully at least once. (You can check if the #initialized property returns `False`
    to see if the #RuntimeError would be raised).
    """

    if self._current is None:
      self.next()
      assert self._current is not None
    return self._current

  def next(self,
    select: t.Optional[t.Collection[T]] = None,
    unselect: t.Optional[t.Collection[T]] = None,
    expect: t.Optional[t.Collection[T]] = None,
  ) -> Token[T, U]:
    """
    Extracts the next token from the text and returns it. Without arguments, all currently
    non-ignored rules are considered. You may use the arguments to further reduce the set of
    rules used for parsing.

    If no token can be extracted using the specified rule subset, the tokenizer will attempt
    to tokenize using the remaining set of rules. If the extracted token is skippable, the next
    token will be extracted recursively. If the extracted token is not skippable, an
    #UnexpectedTokenError is raised.

    Note that the order in which rules are checked is always fixed to the order in which they
    occur on the rule set.

    # Arguments

    select (list): A list of token types that will be prioritized for extracting the next token.
      All token types passed into the *select* argument are taken into account as if they were
      also supplied to the *expect* argument.

    unselect (list): A list of token types that will be deprioritized for extracting the next
      token. The remaining token types are taken into account as if they were also supplied to the
      *expect* argument. The argument cannot be mixed with *select*.

    expect (list): A list of token types that are expected to be returned from this call. If the
      extracted token is not one of the specified token types, an #UnexpectedTokenError is raised.
      Skippable tokens are not skipped if they are expected via this argument.

    # Raises

    TokenizationError: If no token could be extracted from the current possition of the #scanner.

    UnexpectedTokenError: If the extracted token is not of one of the expected token types as
      specified via the *select*, *unselect* or *expect* arguments.

    ValueError: If one of the token types passed to *select*, *unselect* or *expect* is not a
      known token type.
    """

    if select is not None and unselect is not None:
      raise ValueError('`select` and `unselect` arguments cannot be mixed')

    if unselect is not None:
      unselect_set = set(unselect)
      self.rules.check_has_token_types(unselect_set)
      select = self.rules.token_types - unselect_set
    if select is not None:
      select_set = set(select)
      self.rules.check_has_token_types(select_set)
      expect = (t.cast(t.Set[T], set()) if expect is None else set(expect)) | select_set
    if expect is not None:
      if not isinstance(expect, set):
        expect = set(expect)
      self.rules.check_has_token_types(expect)

    if self.debug & Debug.NEXT_ARGS:
      self.log.debug('Tokenizer.next() computed arguments (select=%r, expect=%r)', select, expect)

    self._current = self._do_next(t.cast(t.Optional[t.Set[T]], select), expect)
    return self._current

  def _do_next(self, select: t.Optional[t.Set[T]], expect: t.Optional[t.Set[T]]) -> Token[T, U]:  # NOSONAR
    token, skippable = self._extract_token(lambda t: (select is None and not self.ignored.get(t, False)) or (select is not None and t in select))
    if token is None and select is not None:
      # Extract one of the unselected token types. If that token is skippable, we will accept
      # and skip it. If not, it will cause an #UnexpectedTokenError below given how we set up
      # the "expect" variable.
      token, skippable = self._extract_token(lambda t: select is not None and t not in select and not self.ignored.get(t, False))
      if token is not None and skippable:
        if self.debug & Debug.EXTRACT:
          self.log.debug('No selected token matched, but extract another skippable token "%s". '
            'Skip and continue recursively\n\t\ttoken: %r', token.type, token)
        return self._do_next(select, expect)
    elif token is not None and (expect is None or token.type not in expect) and skippable:
      if self.debug & Debug.EXTRACT:
        self.log.debug('Extracted skippable token "%s". Skip and continue recursively\n\t\ttoken: %r', token.type, token)
      return self._do_next(select, expect)

    if token is None:
      raise TokenizationError(self.scanner.pos)

    if self.debug & Debug.EXTRACT:
      self.log.debug('Extracted token "%s"\n\t\ttoken: %r', token.type, token)

    if expect is not None and token.type not in expect:
      raise UnexpectedTokenError(token, expect)

    return token

  def _extract_token(self, filter: t.Callable[[T], bool]) -> t.Tuple[t.Optional[Token[T, U]], bool]:
    if not self.scanner:
      return Token(
        self.rules.sentinel.type,
        self.rules.sentinel.value,
        self.scanner.pos,
        True), False

    token_pos = self.scanner.pos
    for rule in self.rules:
      if not filter(rule.type) or rule == self._skip_rule_once:
        continue
      token_value = rule.extractor.get_token(self.scanner)
      if token_value is None:
        self.scanner.pos = token_pos
        continue
      token: Token[T, U] = Token(rule.type, token_value, token_pos, False)
      skippable = self.skipped.get(rule.type, rule.skip)
      if not token.value:
        # Zero-length token can only be produced once at a given location.
        # TODO(NiklasRosenstein): This only really works with strings as the token value.
        self._skip_rule_once = rule
      else:
        self._skip_rule_once = None
      return token, skippable
    return None, False

  Debug = Debug  # NOSONAR
  Error = TokenizationError
  Unexpected = UnexpectedTokenError
