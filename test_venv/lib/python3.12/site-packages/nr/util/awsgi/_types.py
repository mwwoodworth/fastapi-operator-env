
import typing_extensions as te


class ASGIApp(te.Protocol):

  def __call__(self, scope, receive, send):
    raise NotImplementedError


class WSGIApp(te.Protocol):

  def __call__(self, environ, start_response):
    raise NotImplementedError
