"""Route modules for BrainOps API."""

from .agents import router as agents
from .auth import router as auth
from .memory import router as memory
from .tasks import router as tasks
from .webhooks import router as webhooks
from .auth_extended import router as auth_extended
from .users import router as users
from .projects import router as projects
from .ai_services import router as ai_services
from .automation import router as automation
from .marketplace import router as marketplace

__all__ = [
    "agents", "auth", "memory", "tasks", "webhooks",
    "auth_extended", "users", "projects", "ai_services", 
    "automation", "marketplace"
]