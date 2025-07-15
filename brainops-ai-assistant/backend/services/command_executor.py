"""Command execution service with safety controls."""

from __future__ import annotations

import asyncio
import os
import signal
import shlex
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from loguru import logger

from core.config import settings
from utils.safety import SafetyChecker
from utils.audit import AuditLogger


class CommandExecutor:
    """Execute system commands with safety checks and logging."""
    
    def __init__(self):
        self.safety_checker = SafetyChecker()
        self.audit = AuditLogger()
        self.allowed_commands = set(settings.ALLOWED_COMMANDS)
        self.timeout = settings.COMMAND_TIMEOUT_SECONDS
    
    def _validate_command(self, command: str, args: List[str]) -> Tuple[bool, str]:
        """Validate if command is allowed and safe."""
        # Check if base command is allowed
        if command not in self.allowed_commands:
            return False, f"Command '{command}' is not in allowed list"
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "rm -rf /",
            ":(){ :|:& };:",  # Fork bomb
            "> /dev/sda",
            "dd if=/dev/zero",
            "chmod -R 777 /",
            "chown -R",
            "mkfs",
            "format"
        ]
        
        full_command = f"{command} {' '.join(args)}"
        for pattern in dangerous_patterns:
            if pattern in full_command:
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Check for sudo (should be handled separately)
        if command == "sudo" or "sudo" in args:
            return False, "Sudo commands must be handled through privileged operations"
        
        return True, ""
    
    async def execute(
        self,
        command: str,
        args: List[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        require_confirmation: bool = None
    ) -> Dict[str, Any]:
        """Execute a command with safety checks."""
        args = args or []
        
        # Validate command
        is_valid, error_msg = self._validate_command(command, args)
        if not is_valid:
            await self.audit.log_command_execution(
                command=command,
                args=args,
                success=False,
                error=error_msg
            )
            return {
                "success": False,
                "error": error_msg,
                "command": command,
                "args": args
            }
        
        # Check if confirmation required
        if require_confirmation is None:
            require_confirmation = await self.safety_checker.requires_confirmation(
                command, args
            )
        
        if require_confirmation:
            return {
                "success": False,
                "requires_confirmation": True,
                "command": command,
                "args": args,
                "message": "This command requires confirmation before execution"
            }
        
        # Validate working directory
        if cwd:
            cwd_path = Path(cwd).resolve()
            if not str(cwd_path).startswith(str(settings.OPS_ROOT_DIR)):
                return {
                    "success": False,
                    "error": "Working directory must be within ops root",
                    "cwd": cwd
                }
        else:
            cwd = str(settings.OPS_ROOT_DIR)
        
        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)
        
        # Build full command
        full_command = [command] + args
        
        try:
            # Log command start
            start_time = datetime.now()
            await self.audit.log_command_execution(
                command=command,
                args=args,
                cwd=cwd,
                status="started"
            )
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                # Kill the process
                process.kill()
                await process.wait()
                
                error_msg = f"Command timed out after {self.timeout} seconds"
                await self.audit.log_command_execution(
                    command=command,
                    args=args,
                    success=False,
                    error=error_msg,
                    duration=(datetime.now() - start_time).total_seconds()
                )
                
                return {
                    "success": False,
                    "error": error_msg,
                    "command": command,
                    "args": args,
                    "timeout": True
                }
            
            # Get result
            duration = (datetime.now() - start_time).total_seconds()
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            # Log completion
            await self.audit.log_command_execution(
                command=command,
                args=args,
                success=process.returncode == 0,
                exit_code=process.returncode,
                stdout_lines=stdout_text.count('\n'),
                stderr_lines=stderr_text.count('\n'),
                duration=duration
            )
            
            return {
                "success": process.returncode == 0,
                "command": command,
                "args": args,
                "exit_code": process.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            await self.audit.log_command_execution(
                command=command,
                args=args,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "args": args
            }
    
    async def execute_script(
        self,
        script_path: str,
        interpreter: str = "bash",
        args: List[str] = None
    ) -> Dict[str, Any]:
        """Execute a script file."""
        # Validate script path
        script = Path(script_path).resolve()
        if not str(script).startswith(str(settings.OPS_ROOT_DIR)):
            return {
                "success": False,
                "error": "Script must be within ops directory"
            }
        
        if not script.exists():
            return {
                "success": False,
                "error": "Script not found"
            }
        
        # Execute using interpreter
        return await self.execute(
            interpreter,
            [str(script)] + (args or []),
            cwd=str(script.parent)
        )
    
    async def execute_pipeline(
        self,
        commands: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a pipeline of commands."""
        results = []
        
        for i, cmd_spec in enumerate(commands):
            command = cmd_spec.get("command")
            args = cmd_spec.get("args", [])
            
            # Check if should continue on error
            continue_on_error = cmd_spec.get("continue_on_error", False)
            
            # Execute command
            result = await self.execute(command, args)
            results.append(result)
            
            # Stop on error unless specified
            if not result["success"] and not continue_on_error:
                return {
                    "success": False,
                    "error": f"Pipeline failed at step {i + 1}",
                    "command": command,
                    "step": i + 1,
                    "results": results
                }
        
        return {
            "success": True,
            "total_commands": len(commands),
            "results": results
        }
    
    async def get_command_history(
        self,
        limit: int = 50,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get command execution history."""
        return await self.audit.get_command_history(limit, user_id)
    
    async def kill_process(self, pid: int) -> Dict[str, Any]:
        """Kill a process by PID."""
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait a bit
            await asyncio.sleep(1)
            
            # Check if still running
            try:
                os.kill(pid, 0)  # Check if process exists
                # Still running, force kill
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already terminated
            
            await self.audit.log_command_execution(
                command="kill",
                args=[str(pid)],
                success=True
            )
            
            return {
                "success": True,
                "pid": pid,
                "killed": True
            }
            
        except Exception as e:
            await self.audit.log_command_execution(
                command="kill",
                args=[str(pid)],
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "pid": pid
            }
    
    async def check_command_status(self, command: str) -> Dict[str, Any]:
        """Check if a command is available and its version."""
        try:
            # Check if command exists
            result = await self.execute("which", [command])
            if not result["success"]:
                return {
                    "available": False,
                    "command": command
                }
            
            command_path = result["stdout"].strip()
            
            # Try to get version
            version_result = await self.execute(command, ["--version"])
            version = None
            if version_result["success"]:
                version = version_result["stdout"].split('\n')[0]
            
            return {
                "available": True,
                "command": command,
                "path": command_path,
                "version": version
            }
            
        except Exception as e:
            return {
                "available": False,
                "command": command,
                "error": str(e)
            }