
import logging
import threading
import typing as t

from nr.util.generic import R, T

logger = logging.getLogger(__name__)
Subscriber = t.Callable[['Refreshable[T]'], None]


class Refreshable(t.Generic[T]):

  def __init__(self, initial: T) -> None:
    self._lock = threading.Lock()
    self._current = initial
    self._subscribers: t.List[Subscriber] = []

  def __getstate__(self):
    return self, (self._current, self._subscribers)

  def __setstate__(self, state):
    self._lock = threading.Lock()
    self._current, self._subscribers = state[1]

  def get(self) -> T:
    with self._lock:
      return self._current

  def update(self, value: T) -> None:
    with self._lock:
      self._current = value
      subscribers = self._subscribers[:]
    for subscriber in subscribers:
      try:
        subscriber(self)
      except:
        logger.exception('Error in subscriber')

  def subscribe(self, subscriber: Subscriber) -> None:
    with self._lock:
      self._subscribers.append(subscriber)
    try:
      subscriber(self)
    except:
      logger.exception('Error in subscriber')

  def map(self, mapper: t.Callable[[T], R]) -> 'Refreshable[R]':
    """
    Map the value of the refreshable to a new refreshable that automatically gets updated when the
    parent is updated. Be aware that this method should be used sparingly as it registers a new
    subscriber to this refreshable that will never be disposed of again.
    """

    child = Refreshable(mapper(self.get()))
    def refresh(_parent):
      child.update(mapper(self.get()))
    self.subscribe(refresh)
    return child
