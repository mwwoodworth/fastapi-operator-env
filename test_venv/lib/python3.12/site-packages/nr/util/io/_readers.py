# -*- coding: utf-8 -*-
# Copyright (c) 2020 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import codecs
import io
import sys
from typing import TextIO


class EncodedStreamReader(io.BufferedIOBase):
  """
  A readable file-like object that wraps a #TextIO object and converts it to a binary stream encoded with the specified
  *encoding* (or the default system encoding).

  Example:

  ```py
  import io
  from nr.utils.io.readers import EncodedStreamReader
  fp = EncodedStreamReader(io.StringIO('äöü'), 'utf-8')
  assert fp.read(1) == b'\xc3'
  assert fp.read(1) == b'\xa4'
  ```
  """

  def __init__(self, stream: TextIO, encoding: str = None, errors: str = 'strict'):
    encoding = encoding or getattr(stream, 'encoding', None) or sys.getdefaultencoding()
    self._stream = stream
    self._encoder = codecs.getencoder(encoding)
    self._errors = errors
    self._buffer = b''
    self.encoding = encoding

  def fileno(self):
    return self._stream.fileno()

  def read(self, n: int = None) -> bytes:
    if self._buffer and n is None:
      result, self._buffer = self._buffer, b''
    elif self._buffer:
      assert n is not None
      result, self._buffer = self._buffer[:n], self._buffer[n:]
      n -= len(result)
    else:
      result = b''
    if n is None or n >= 0:
      assert not self._buffer
      data = self._encoder(self._stream.read(-1 if n is None else n), self._errors)[0]
      if n is not None and len(data) > n:
        data, self._buffer = data[:n], data[n:]
      result += data
    return result
