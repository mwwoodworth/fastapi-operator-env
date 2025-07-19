
from __future__ import annotations

import logging


class SimpleFilter(logging.Filter):

  def __init__(self, name: str = '', contains: str | None = None, not_contains: str | None = None) -> None:
    super().__init__()
    self.contains = contains
    self.not_contains = not_contains

  def filter(self, record: logging.LogRecord) -> bool:
    if not super().filter(record):
      return False
    if self.contains and self.contains not in record.msg:
      return False
    if self.not_contains and self.not_contains  in record.msg:
      return False
    return True
