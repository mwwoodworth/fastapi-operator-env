
from __future__ import annotations

import logging
import types
import typing as t

from nr.util.generic import T

logger = logging.getLogger(__name__)


class PluginRegistry:
  """ A helper class to register plugins associated with a unique identifier and later access them. """

  def __init__(self) -> None:
    self._groups: dict[t.Hashable, list[tuple[str, t.Any]]] = {}

  @t.overload
  def group(self, group: t.Hashable, base_class: type[T]) -> t.Iterable[tuple[str, T]]: ...

  @t.overload
  def group(self, group: t.Hashable) -> t.Iterable[tuple[str, t.Any]]: ...

  def group(self, group, base_class=None):
    plugins = list(self._groups.get(group, []))
    for idx, (plugin_name, plugin) in enumerate(plugins):
      if isinstance(plugin, (types.FunctionType, types.MethodType, types.LambdaType)):
        try:
          plugin = plugin()
        except:
          logger.exception('Unable to instanciate plugin "%s" (in group: "%s")', plugin_name, group)
          continue
      plugins[idx] = (plugin_name, plugin)

    if base_class is not None:
      assert isinstance(base_class, type), type(base_class)
      for idx, (plugin_name, plugin) in enumerate(plugins):
        if not isinstance(plugin, base_class):
          logger.error(
            'Plugin "%s" (registered in group: "%s") is not an instance of %s',
            plugin_name, group, base_class.__name__
          )
          continue
        plugins[idx] = (plugin_name, plugin)

    return plugins

  def register(self, group: t.Hashable, name: str, plugin: t.Any | t.Callable[[], t.Any]) -> None:
    """ Register a plugin under the specified *group* and *name*. If the *plugin* is callable (i.e. a function,
    method or lambda), it will be called with no arguments everytime #group() is called with the expectation to
    return an actual instance of the plugin. Registering multiple plugins with the same *name* in the same *group*
    causes that plugin to be registered multiple times (instead of replacing the previously registered plugin). """

    self._groups.setdefault(group, []).append((name, plugin))
