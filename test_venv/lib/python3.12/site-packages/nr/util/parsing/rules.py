
import re
import typing as t

from ._tokenizer.extractor import TokenExtractor

if t.TYPE_CHECKING:
  from ._scanner import Scanner


def regex(pattern: str, *, at_line_start_only: bool = False) -> TokenExtractor['re.Match']:
  """
  Creates a tokenizer rule that matches a regular expression and returns the #re.Match object
  as the token value. If you want the pattern to match at the start of a line only, set the
  *at_line_start_only* argument to `True`. The regex caret (`^`) control character will not work
  because the regex is matched from the cursor's current position and not the line start.
  """

  def _impl(scanner: 'Scanner') -> t.Optional['re.Match']:
    if at_line_start_only and scanner.pos.column != 1:
      return None
    match = scanner.match(pattern)
    if match is None:
      return None
    return match

  return TokenExtractor.of(_impl)


def regex_extract(pattern: str, group: t.Union[str, int] = 0, *,
    at_line_start_only: bool = False) -> TokenExtractor[str]:
  """
  Creates a token extractor that matches a regular expression and extracts a group from the match
  as the token value.
  """

  return regex(pattern, at_line_start_only=at_line_start_only).map(lambda m: m.group(group))


def string_literal(
  accepted_prefixes: t.Optional[str] = 'bfru',
  quote_sequences: t.Sequence[str] = ('"""', "'''", '"', "'"),
) -> TokenExtractor[str]:
  """
  Matches a Python string literal.
  """

  def _impl(scanner: 'Scanner') -> t.Optional[str]:
    prefix = (scanner.getmatch(r'[' + re.escape(accepted_prefixes) + r']+') or '') \
        if accepted_prefixes else ''
    quote_type = scanner.getmatch(r'(' + r'|'.join(re.escape(s) for s in quote_sequences) + r')')
    if not quote_type:
      return None
    is_multiline = len(quote_type) > 1
    contents = ''
    while scanner.char and (is_multiline or scanner.char != '\n'):
      if scanner.match(re.escape(quote_type)):
        break
      contents += scanner.char
      if scanner.char == '\\':
        contents += scanner.next()
      scanner.next()
    else:
      return None
    return prefix + quote_type + contents + quote_type

  return TokenExtractor.of(_impl)
