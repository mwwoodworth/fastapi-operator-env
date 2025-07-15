"""File operations service with safety checks."""

from __future__ import annotations

import os
import shutil
import aiofiles
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from loguru import logger

from core.config import settings
from utils.safety import SafetyChecker
from utils.audit import AuditLogger


class FileOperationsService:
    """Secure file operations within allowed directories."""
    
    def __init__(self):
        self.safety_checker = SafetyChecker()
        self.audit = AuditLogger()
        self.ops_root = settings.OPS_ROOT_DIR
        
        # Ensure ops directory exists
        self.ops_root.mkdir(parents=True, exist_ok=True)
    
    def _validate_path(self, path: str) -> Path:
        """Validate and normalize file path."""
        # Convert to Path object
        file_path = Path(path)
        
        # If relative, make it relative to ops root
        if not file_path.is_absolute():
            file_path = self.ops_root / file_path
        
        # Resolve to absolute path
        file_path = file_path.resolve()
        
        # Ensure it's within ops root
        if not str(file_path).startswith(str(self.ops_root)):
            raise PermissionError(f"Access denied: Path outside ops directory")
        
        return file_path
    
    def _check_file_type(self, path: Path) -> bool:
        """Check if file type is allowed."""
        if path.suffix.lower() not in settings.ALLOWED_FILE_EXTENSIONS:
            return False
        return True
    
    async def read_file(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read a file safely."""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": "File not found",
                    "path": str(file_path)
                }
            
            if not file_path.is_file():
                return {
                    "success": False,
                    "error": "Path is not a file",
                    "path": str(file_path)
                }
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                return {
                    "success": False,
                    "error": f"File too large (>{settings.MAX_FILE_SIZE_MB}MB)",
                    "size": file_size
                }
            
            # Read file
            async with aiofiles.open(file_path, mode='r', encoding=encoding) as f:
                content = await f.read()
            
            # Log the operation
            await self.audit.log_file_operation(
                operation="read",
                path=str(file_path),
                success=True
            )
            
            return {
                "success": True,
                "content": content,
                "path": str(file_path),
                "size": file_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                "mime_type": mimetypes.guess_type(str(file_path))[0]
            }
            
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            await self.audit.log_file_operation(
                operation="read",
                path=path,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> Dict[str, Any]:
        """Write content to a file safely."""
        try:
            file_path = self._validate_path(path)
            
            # Check file type
            if not self._check_file_type(file_path):
                return {
                    "success": False,
                    "error": f"File type not allowed: {file_path.suffix}"
                }
            
            # Create parent directories if needed
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists (for audit)
            existed = file_path.exists()
            
            # Write file
            async with aiofiles.open(file_path, mode='w', encoding=encoding) as f:
                await f.write(content)
            
            # Log the operation
            await self.audit.log_file_operation(
                operation="write",
                path=str(file_path),
                success=True,
                details={
                    "created": not existed,
                    "size": len(content),
                    "lines": content.count('\n') + 1
                }
            )
            
            return {
                "success": True,
                "path": str(file_path),
                "created": not existed,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            await self.audit.log_file_operation(
                operation="write",
                path=path,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_file(self, path: str, require_confirmation: bool = True) -> Dict[str, Any]:
        """Delete a file safely."""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": "File not found"
                }
            
            # Safety check for important files
            if await self.safety_checker.is_protected_file(str(file_path)):
                return {
                    "success": False,
                    "error": "Cannot delete protected file",
                    "require_confirmation": True
                }
            
            # Get file info before deletion
            file_info = {
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            
            # Delete file or directory
            if file_path.is_dir():
                shutil.rmtree(file_path)
                operation = "delete_directory"
            else:
                file_path.unlink()
                operation = "delete_file"
            
            # Log the operation
            await self.audit.log_file_operation(
                operation=operation,
                path=str(file_path),
                success=True,
                details=file_info
            )
            
            return {
                "success": True,
                "path": str(file_path),
                "deleted": True,
                "info": file_info
            }
            
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            await self.audit.log_file_operation(
                operation="delete",
                path=path,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_directory(self, path: str) -> Dict[str, Any]:
        """Create a directory."""
        try:
            dir_path = self._validate_path(path)
            
            if dir_path.exists():
                return {
                    "success": False,
                    "error": "Directory already exists"
                }
            
            # Create directory
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Log the operation
            await self.audit.log_file_operation(
                operation="create_directory",
                path=str(dir_path),
                success=True
            )
            
            return {
                "success": True,
                "path": str(dir_path),
                "created": True
            }
            
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            await self.audit.log_file_operation(
                operation="create_directory",
                path=path,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_directory(
        self,
        path: str = "",
        pattern: str = "*",
        recursive: bool = False
    ) -> Dict[str, Any]:
        """List directory contents."""
        try:
            dir_path = self._validate_path(path)
            
            if not dir_path.exists():
                return {
                    "success": False,
                    "error": "Directory not found"
                }
            
            if not dir_path.is_dir():
                return {
                    "success": False,
                    "error": "Path is not a directory"
                }
            
            # List files
            files = []
            if recursive:
                for item in dir_path.rglob(pattern):
                    files.append(self._get_file_info(item))
            else:
                for item in dir_path.glob(pattern):
                    files.append(self._get_file_info(item))
            
            # Sort by name
            files.sort(key=lambda x: x["name"])
            
            return {
                "success": True,
                "path": str(dir_path),
                "files": files,
                "count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy a file or directory."""
        try:
            src_path = self._validate_path(source)
            dst_path = self._validate_path(destination)
            
            if not src_path.exists():
                return {
                    "success": False,
                    "error": "Source not found"
                }
            
            # Check file type for destination
            if src_path.is_file() and not self._check_file_type(dst_path):
                return {
                    "success": False,
                    "error": f"Destination file type not allowed: {dst_path.suffix}"
                }
            
            # Copy
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path)
                operation = "copy_directory"
            else:
                shutil.copy2(src_path, dst_path)
                operation = "copy_file"
            
            # Log the operation
            await self.audit.log_file_operation(
                operation=operation,
                path=str(src_path),
                success=True,
                details={"destination": str(dst_path)}
            )
            
            return {
                "success": True,
                "source": str(src_path),
                "destination": str(dst_path),
                "copied": True
            }
            
        except Exception as e:
            logger.error(f"Error copying {source} to {destination}: {e}")
            await self.audit.log_file_operation(
                operation="copy",
                path=source,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move/rename a file or directory."""
        try:
            src_path = self._validate_path(source)
            dst_path = self._validate_path(destination)
            
            if not src_path.exists():
                return {
                    "success": False,
                    "error": "Source not found"
                }
            
            # Check file type for destination
            if src_path.is_file() and not self._check_file_type(dst_path):
                return {
                    "success": False,
                    "error": f"Destination file type not allowed: {dst_path.suffix}"
                }
            
            # Move
            shutil.move(str(src_path), str(dst_path))
            
            # Log the operation
            await self.audit.log_file_operation(
                operation="move",
                path=str(src_path),
                success=True,
                details={"destination": str(dst_path)}
            )
            
            return {
                "success": True,
                "source": str(src_path),
                "destination": str(dst_path),
                "moved": True
            }
            
        except Exception as e:
            logger.error(f"Error moving {source} to {destination}: {e}")
            await self.audit.log_file_operation(
                operation="move",
                path=source,
                success=False,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_files(
        self,
        pattern: str,
        content_search: Optional[str] = None,
        path: str = ""
    ) -> Dict[str, Any]:
        """Search for files by name pattern and optionally content."""
        try:
            search_path = self._validate_path(path)
            
            if not search_path.exists():
                return {
                    "success": False,
                    "error": "Search path not found"
                }
            
            matches = []
            
            # Search by filename pattern
            for file_path in search_path.rglob(pattern):
                if file_path.is_file():
                    match_info = self._get_file_info(file_path)
                    
                    # Search content if requested
                    if content_search and self._check_file_type(file_path):
                        try:
                            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                                content = await f.read()
                                if content_search.lower() in content.lower():
                                    # Find line numbers
                                    lines = content.split('\n')
                                    matching_lines = []
                                    for i, line in enumerate(lines):
                                        if content_search.lower() in line.lower():
                                            matching_lines.append({
                                                "line": i + 1,
                                                "content": line.strip()[:100]
                                            })
                                    
                                    match_info["content_matches"] = matching_lines[:5]
                                    matches.append(match_info)
                        except:
                            # Skip files that can't be read as text
                            pass
                    else:
                        matches.append(match_info)
            
            return {
                "success": True,
                "pattern": pattern,
                "content_search": content_search,
                "matches": matches,
                "count": len(matches)
            }
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_file_info(self, path: Path) -> Dict[str, Any]:
        """Get file information."""
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "mime_type": mimetypes.guess_type(str(path))[0] if path.is_file() else None
        }