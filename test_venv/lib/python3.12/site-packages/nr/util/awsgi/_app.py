
from __future__ import annotations

from ._types import ASGIApp, WSGIApp


class App:
  """
  Base for ASGI/WSGI applications. The class instance itself is not the ASGI/WSGI app, but instead it is expected to
  provide that object after and initialization procedure. An #App subclass should encapsulate all logic for the
  entirety of the application.
  """

  asgi_app: ASGIApp | None = None
  wsgi_app: WSGIApp | None = None

  def initialize(self) -> None:
    """ Delayed initializer, called after the app is handed to the ASGI/WSGI runner to avoid pickling errors. """
