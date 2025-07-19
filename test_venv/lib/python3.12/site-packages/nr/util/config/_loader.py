
from __future__ import annotations

import logging
import typing as t
from pathlib import Path

import databind.json  # type: ignore[import]
import yaml  # type: ignore[import]
from databind.core.annotations import collect_unknowns  # type: ignore[import]

from nr.util.generic import T

logger = logging.getLogger(__name__)


class ConfigLoader:

  def __init__(
    self,
    filename: str,
    encoding: str = 'utf8',
    allow_unknown_keys: bool = False,
  ) -> None:
    self.filename = Path(filename)
    self.encoding = encoding
    self.allow_unknown_keys = allow_unknown_keys
    self.last_load_mtime: t.Optional[float] = None

  def load_config(self, model: type[T]) -> T:
    data = yaml.safe_load(self.filename.read_text(encoding=self.encoding))
    unknowns = collect_unknowns()
    annotations = [unknowns] if self.allow_unknown_keys else []
    config = databind.json.load(data, model, filename=str(self.filename), annotations=annotations)
    if unknowns.entries:
      logger.warning('Found unknown configuration keys in "%s": %s', self.filename, unknowns.entries)
    self.last_load_mtime = self.filename.stat().st_mtime
    return config

  def changed(self) -> bool:
    if self.last_load_mtime is None:
      return True
    try:
      return self.filename.stat().st_mode > self.last_load_mtime
    except FileNotFoundError:
      return True
