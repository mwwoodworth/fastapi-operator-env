"""Safety checker for operations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any, List

from core.config import settings


class SafetyChecker:
    """Check operations for safety and security risks."""
    
    def __init__(self):
        # Protected files and directories
        self.protected_paths = {
            ".env",
            ".env.local",
            ".env.production",
            "config.json",
            "secrets.json",
            ".git",
            ".ssh",
            "node_modules",
            "__pycache__",
            "venv",
            ".venv"
        }
        
        # Dangerous command patterns
        self.dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r":\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
            r">\s*/dev/[a-z]+",
            r"dd\s+if=/dev/zero",
            r"chmod\s+-R\s+777",
            r"chown\s+-R",
            r"mkfs",
            r"format\s+[a-zA-Z]:",
            r"del\s+/s\s+/q",
            r"wget.*\|\s*sh",
            r"curl.*\|\s*bash",
        ]
        
        # Actions that always require confirmation
        self.confirmation_required = {
            "file_delete",
            "command_execute",
            "deploy",
            "backup",
            "restore",
            "workflow_create"
        }
    
    async def is_safe(self, action: Dict[str, Any]) -> bool:
        """Check if an action is safe to execute."""
        action_type = action.get("type", "")
        
        # Check file operations
        if action_type.startswith("file_"):
            return await self._check_file_safety(action)
        
        # Check command operations
        if action_type == "command_execute":
            return await self._check_command_safety(action)
        
        # Check workflow operations
        if action_type.startswith("workflow_"):
            return await self._check_workflow_safety(action)
        
        # Default to safe for other operations
        return True
    
    async def _check_file_safety(self, action: Dict[str, Any]) -> bool:
        """Check file operation safety."""
        path = action.get("path", "")
        
        # Check if path is protected
        if await self.is_protected_file(path):
            return False
        
        # Check file size for write operations
        if action.get("type") == "file_write":
            content = action.get("content", "")
            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                return False
        
        return True
    
    async def _check_command_safety(self, action: Dict[str, Any]) -> bool:
        """Check command execution safety."""
        command = action.get("command", "")
        args = action.get("args", [])
        
        # Build full command
        full_command = f"{command} {' '.join(args)}"
        
        # Check against dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, full_command, re.IGNORECASE):
                return False
        
        # Check if command is allowed
        if command not in settings.ALLOWED_COMMANDS:
            return False
        
        return True
    
    async def _check_workflow_safety(self, action: Dict[str, Any]) -> bool:
        """Check workflow operation safety."""
        workflow = action.get("workflow", {})
        
        # Check workflow steps
        for step in workflow.get("steps", []):
            if step.get("type") == "command":
                if not await self._check_command_safety(step):
                    return False
            elif step.get("type") == "file_operation":
                if not await self._check_file_safety(step):
                    return False
        
        return True
    
    async def is_protected_file(self, path: str) -> bool:
        """Check if a file/directory is protected."""
        path_obj = Path(path)
        
        # Check exact matches
        if path_obj.name in self.protected_paths:
            return True
        
        # Check if any parent is protected
        for parent in path_obj.parents:
            if parent.name in self.protected_paths:
                return True
        
        # Check patterns
        protected_patterns = [
            r"\.env.*",
            r".*\.key$",
            r".*\.pem$",
            r".*_rsa$",
            r".*\.crt$",
            r".*secret.*",
            r".*password.*",
            r".*token.*",
            r".*credential.*"
        ]
        
        for pattern in protected_patterns:
            if re.match(pattern, path_obj.name, re.IGNORECASE):
                return True
        
        return False
    
    async def requires_confirmation(self, command: str, args: List[str]) -> bool:
        """Check if a command requires user confirmation."""
        # Destructive commands
        if command in ["rm", "del", "rmdir"]:
            return True
        
        # System modification commands
        if command in ["chmod", "chown", "ln"]:
            return True
        
        # Package management
        if command in ["npm", "pip", "apt", "yum", "brew"]:
            if any(arg in ["install", "uninstall", "remove", "update", "upgrade"] for arg in args):
                return True
        
        # Git operations that modify history
        if command == "git":
            if any(arg in ["push", "force", "reset", "rebase"] for arg in args):
                return True
        
        # Docker/Kubernetes operations
        if command in ["docker", "kubectl"]:
            if any(arg in ["rm", "delete", "stop", "kill"] for arg in args):
                return True
        
        return False
    
    def sanitize_path(self, path: str) -> str:
        """Sanitize a file path."""
        # Remove any attempts at directory traversal
        path = path.replace("..", "")
        path = path.replace("~", "")
        
        # Remove leading slashes to make relative
        path = path.lstrip("/")
        
        return path
    
    def sanitize_command_args(self, args: List[str]) -> List[str]:
        """Sanitize command arguments."""
        sanitized = []
        
        for arg in args:
            # Remove shell metacharacters
            arg = re.sub(r'[;&|`$<>]', '', arg)
            
            # Remove quotes that might break out
            arg = arg.replace('"', '').replace("'", '')
            
            sanitized.append(arg)
        
        return sanitized