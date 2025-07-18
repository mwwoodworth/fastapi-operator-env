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
from .erp_estimating import router as erp_estimating
from .erp_job_management import router as erp_job_management
from .erp_field_capture import router as erp_field_capture
from .erp_compliance import router as erp_compliance
from .erp_task_management import router as erp_task_management
from .erp_financial import router as erp_financial

__all__ = [
    "agents", "auth", "memory", "tasks", "webhooks",
    "auth_extended", "users", "projects", "ai_services", 
    "automation", "marketplace", "erp_estimating",
    "erp_job_management", "erp_field_capture", "erp_compliance",
    "erp_task_management", "erp_financial"
]