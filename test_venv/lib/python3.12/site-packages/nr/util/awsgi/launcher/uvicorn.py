
from __future__ import annotations

import dataclasses
import sys
import typing as t

from . import AWSGILauncher


@dataclasses.dataclass
class UvicornLauncher(AWSGILauncher):
  """
  Launches your ASGI/WSGI application via Uvicorn.
  """

  # TODO (@NiklasRosenstein): Ensure that Uvicorn access/error logs end up in var/log

  #: Bind socket to this host.
  host: str | None = None

  #: Bind socket to this port.
  port: int | None = 8000

  #: Bind to a UNIX domain socket.
  unix_socket: str | None = None

  #: Number of worker processes.
  workers: int | None = None

  #: Enable auto-reload.
  reload: bool = False

  #: Event loop implementation.
  loop: str = 'auto'

  #: HTTP protocol implementation.
  http: str = 'auto'

  #: Additional keyword arguments for the Uvicorn invokation.
  kwargs: dict[str, t.Any] = dataclasses.field(default_factory=dict)

  #: The entrypoint to launch.
  entrypoint: str | None = None

  def launch(self, entrypoint: str, factory: bool = False) -> None:
    import uvicorn  # type: ignore
    try:
      sys.exit(uvicorn.run(
        entrypoint,
        host=self.host,
        port=self.port,
        uds=self.unix_socket,
        workers=self.workers,
        reload=self.reload,
        loop=self.loop,
        http=self.http,
        factory=factory,
      ))
    except KeyboardInterrupt:
      sys.exit(1)
