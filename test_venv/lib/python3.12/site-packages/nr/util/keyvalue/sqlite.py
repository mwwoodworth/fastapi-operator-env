
""" A key-value store implementation based on sqlite3. """

from __future__ import annotations

import contextlib
import math
import sqlite3
import string
import threading
import time
import typing as t

from ._api import KeyValueStore


def _fetch_all(cursor: sqlite3.Cursor) -> t.Iterable[tuple]:
  while True:
    rows = cursor.fetchmany()
    print(rows)
    if not rows:
      break
    yield from rows


class SqliteDatastore:
  """
  Provider for key-value datastores backed by an SQLite3 database.

  The #SqliteDatastore is thread-safe, but may be slow to access concurrently due to locking requirements.
  """

  NAMESPACE_CHARS = frozenset(string.ascii_letters + string.digits + '._-')

  def __init__(self, filename: str) -> None:
    self._lock = threading.Lock()
    self._conn = sqlite3.connect(filename, check_same_thread=False)
    self._created_namespaces: t.Set[str] = set()

  @staticmethod
  def _get_time(add: int) -> int:
    return int(math.ceil(time.time() + add))

  @staticmethod
  def _validate_namespace(namespace: str) -> None:
    if set(namespace) - SqliteDatastore.NAMESPACE_CHARS:
      raise ValueError(f'invalid namespace name: {namespace!r}')

  @staticmethod
  def _get_namespaces(cursor: sqlite3.Cursor) -> t.Iterable[str]:
    cursor.execute('''SELECT name FROM sqlite_master
      WHERE type = 'table' AND name NOT like 'sqlite_%';''')
    yield from (x[0] for x in _fetch_all(cursor))

  @contextlib.contextmanager
  def _locked_cursor(self) -> t.Iterator[sqlite3.Cursor]:
    with self._lock, contextlib.closing(self._conn.cursor()) as cursor:
      yield cursor

  def get_namespaces(self) -> t.Iterator[str]:
    """
    Returns an iterator that returns the name of all namespaces known to the Sqlite store. Note
    that new namespaces are created on-deman using #store().
    """

    with self._locked_cursor() as cursor:
      yield from self._get_namespaces(cursor)

  def get_keys(self, namespace: str, prefix: str) -> t.Iterator[tuple[str, int | None]]:
    """
    Returns an iterator that returns all keys in the specified *namespace* and their expiration
    timestamp. This excludes any keys that are already expired but not yet expunged.
    """

    with self._locked_cursor() as cursor:
      try:
        cursor.execute(f'''
          SELECT key, exp FROM "{namespace}"
          WHERE key LIKE ? AND (exp IS NULL OR exp < ?)
          ''',
          (prefix.replace('%', '%%') + '%', self._get_time(0),))
      except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc):
          raise ValueError(f'namespace {namespace!r} does not exist')
        raise
      yield from t.cast(t.Iterator['tuple[str, int | None]'], _fetch_all(cursor))

  def _ensure_namespace(self, cursor: sqlite3.Cursor, namespace: str) -> None:
    self._validate_namespace(namespace)
    if namespace not in self._created_namespaces:
      cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{namespace}"
        (key TEXT PRIMARY KEY, value BLOB, exp INTEGER)''')
      self._created_namespaces.add(namespace)

  def get(self, namespace: str, key: str) -> bytes:
    self._validate_namespace(namespace)
    with self._locked_cursor() as cursor:
      try:
        cursor.execute(f'''
          SELECT value FROM "{namespace}"
            WHERE key = ? AND (? < exp OR exp IS NULL)''',
          (key, self._get_time(0)),
        )
      except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc):
          raise ValueError(f'namespace {namespace!r} does not exist')
        raise
      result = cursor.fetchone()
      if result is None:
          raise KeyError(f'{namespace} :: {key}')
      if not isinstance(result[0], bytes):
        raise RuntimeError(f'expected data to be bytes, got {type(result[0]).__name__}')
      return result[0]

  def set(self, namespace: str, key: str, value: bytes, expires_in: int | None = None) -> None:
    self._validate_namespace(namespace)
    with self._locked_cursor() as cursor:

      # Create the table for the namespace if it does not exist.
      self._ensure_namespace(cursor, namespace)

      # Insert the value into the database.
      exp = self._get_time(expires_in) if expires_in is not None else None
      cursor.execute(f'''
        INSERT OR REPLACE INTO "{namespace}"
        VALUES (?, ?, ?)''',
        (key, value, exp),
      )

      self._conn.commit()

  def delete(self, namespace: str, key: str) -> None:
    self._validate_namespace(namespace)
    with self._locked_cursor() as cursor:

      # Create the table for the namespace if it does not exist.
      self._ensure_namespace(cursor, namespace)

      # Insert the value into the database.
      cursor.execute(f'DELETE FROM "{namespace}" WHERE key = ?', (key,))

      self._conn.commit()

  def get_namespace(self, namespace: str) -> KeyValueStore:
    with self._locked_cursor() as cursor:
      self._ensure_namespace(cursor, namespace)
    return SqliteNamespace(self, namespace)

  def expunge(self, namespace: t.Optional[str] = None) -> None:
    with self._locked_cursor() as cursor:
      for namespace in [namespace] if namespace else list(self._get_namespaces(cursor)):
        cursor.execute(f'''
          DELETE FROM "{namespace}" WHERE exp < ?''',
          (self._get_time(0),),
        )
      self._conn.commit()


class SqliteNamespace(KeyValueStore):

  def __init__(self, store: SqliteDatastore, namespace: str) -> None:
    self._store = store
    self._namespace = namespace

  def get(self, key: str) -> bytes:
    return self._store.get(self._namespace, key)

  def set(self, key: str, value: bytes, expires_in: int | None = None) -> None:
    self._store.set(self._namespace, key, value, expires_in)

  def delete(self, key: str) -> None:
    self._store.delete(self._namespace, key)

  def keys(self, prefix: str = '') -> t.Iterable[str]:
    for key, _exp in self._store.get_keys(self._namespace, prefix):
      yield key

  def count(self, prefix: str = '') -> int:
    raise NotImplementedError('SqliteNamespace.count() is not implemented')
