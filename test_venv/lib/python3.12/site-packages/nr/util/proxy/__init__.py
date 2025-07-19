
"""
Provides classes that proxy all operations to a delegate object, allowing to implement behaviours at runtime where
the object contained in a "variable" can be interchanged or different based on the async context or thread.
"""

from ._base import BaseProxy, get, get_name
from ._contextlocal import ContextLocalProxy, contextlocal
from ._proxy import Proxy, bind, is_bound, proxy, set_value
from ._stackable import StackableProxy, empty, pop, push
from ._threadlocal import ThreadLocalProxy, threadlocal

__all__ = [
  'get_name', 'get', 'BaseProxy',
  'bind', 'is_bound', 'proxy', 'set_value', 'Proxy',
  'empty', 'push', 'pop', 'StackableProxy',
  'threadlocal', 'ThreadLocalProxy',
  'contextlocal', 'ContextLocalProxy',
]
