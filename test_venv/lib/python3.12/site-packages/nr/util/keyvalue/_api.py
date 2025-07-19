
from __future__ import annotations

import abc
import typing as t

from nr.util.generic import T


class Transaction(abc.ABC):
  """
  Represents a transaction object that can be commited or aborted.
  """

  @abc.abstractmethod
  def commit(self) -> None:
    ...

  @abc.abstractmethod
  def abort(self) -> None:
    ...

  def __enter__(self: T) -> 'T':
    return self

  def __exit__(self, exc_v, exc_t, exc_tb) -> None:
    if exc_v is None:
      self.commit()
    else:
      self.abort()


class KeyValueStore(abc.ABC):
  """
  Interface for key-value stores.
  """

  @abc.abstractmethod
  def get(self, key: str) -> bytes:
    ...

  @abc.abstractmethod
  def set(self, key: str, data: bytes, exp: int | None = None) -> None:
    ...

  @abc.abstractmethod
  def delete(self, key: str) -> None:
    ...

  @abc.abstractmethod
  def keys(self, prefix: str = '') -> t.Iterable[str]:
    ...

  @abc.abstractmethod
  def count(self, prefix: str = '') -> int:
    ...
