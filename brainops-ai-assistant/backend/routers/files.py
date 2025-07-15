"""File operations API endpoints."""

from __future__ import annotations

import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.auth import get_current_user
from services.file_ops import FileOperationsService
from models.db import User
from utils.audit import AuditLogger

router = APIRouter(prefix="/files", tags=["files"])
audit_logger = AuditLogger()

# Initialize services
file_ops = FileOperationsService()


class FileWrite(BaseModel):
    """File write model."""
    content: str = Field(..., description="File content")
    encoding: str = Field(default="utf-8", description="File encoding")
    create_dirs: bool = Field(default=True, description="Create parent directories")


class FileSearch(BaseModel):
    """File search model."""
    pattern: str = Field(..., description="Search pattern")
    content_search: Optional[str] = Field(default=None, description="Content to search for")
    path: str = Field(default="", description="Path to search in")


class DirectoryList(BaseModel):
    """Directory listing model."""
    pattern: str = Field(default="*", description="File pattern")
    recursive: bool = Field(default=False, description="Recursive search")


@router.post("/read")
async def read_file(
    path: str,
    encoding: str = "utf-8",
    current_user: User = Depends(get_current_user)
):
    """Read a file."""
    try:
        result = await file_ops.read_file(path, encoding)
        
        await audit_logger.log_file_operation(
            operation="read",
            path=path,
            user_id=current_user.id,
            success=result["success"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_file(
    path: str,
    file_data: FileWrite,
    current_user: User = Depends(get_current_user)
):
    """Write content to a file."""
    try:
        result = await file_ops.write_file(
            path=path,
            content=file_data.content,
            encoding=file_data.encoding,
            create_dirs=file_data.create_dirs
        )
        
        await audit_logger.log_file_operation(
            operation="write",
            path=path,
            user_id=current_user.id,
            success=result["success"],
            details={"size": len(file_data.content)}
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_file(
    path: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a file or directory."""
    try:
        result = await file_ops.delete_file(path)
        
        await audit_logger.log_file_operation(
            operation="delete",
            path=path,
            user_id=current_user.id,
            success=result["success"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a file."""
    try:
        # Read file content
        content = await file.read()
        
        # Write to specified path
        result = await file_ops.write_file(
            path=path,
            content=content.decode("utf-8"),
            create_dirs=True
        )
        
        await audit_logger.log_file_operation(
            operation="upload",
            path=path,
            user_id=current_user.id,
            success=result["success"],
            details={
                "filename": file.filename,
                "size": len(content),
                "content_type": file.content_type
            }
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download_file(
    path: str,
    current_user: User = Depends(get_current_user)
):
    """Download a file."""
    try:
        # Validate path
        result = await file_ops.read_file(path)
        
        await audit_logger.log_file_operation(
            operation="download",
            path=path,
            user_id=current_user.id,
            success=result["success"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        # Return file response
        return FileResponse(
            path=path,
            filename=os.path.basename(path),
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-directory")
async def create_directory(
    path: str,
    current_user: User = Depends(get_current_user)
):
    """Create a directory."""
    try:
        result = await file_ops.create_directory(path)
        
        await audit_logger.log_file_operation(
            operation="create_directory",
            path=path,
            user_id=current_user.id,
            success=result["success"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list-directory")
async def list_directory(
    path: str = "",
    list_params: DirectoryList = DirectoryList(),
    current_user: User = Depends(get_current_user)
):
    """List directory contents."""
    try:
        result = await file_ops.list_directory(
            path=path,
            pattern=list_params.pattern,
            recursive=list_params.recursive
        )
        
        await audit_logger.log_file_operation(
            operation="list_directory",
            path=path,
            user_id=current_user.id,
            success=result["success"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy")
async def copy_file(
    source: str,
    destination: str,
    current_user: User = Depends(get_current_user)
):
    """Copy a file or directory."""
    try:
        result = await file_ops.copy_file(source, destination)
        
        await audit_logger.log_file_operation(
            operation="copy",
            path=source,
            user_id=current_user.id,
            success=result["success"],
            details={"destination": destination}
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move")
async def move_file(
    source: str,
    destination: str,
    current_user: User = Depends(get_current_user)
):
    """Move/rename a file or directory."""
    try:
        result = await file_ops.move_file(source, destination)
        
        await audit_logger.log_file_operation(
            operation="move",
            path=source,
            user_id=current_user.id,
            success=result["success"],
            details={"destination": destination}
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_files(
    search_params: FileSearch,
    current_user: User = Depends(get_current_user)
):
    """Search for files by name and content."""
    try:
        result = await file_ops.search_files(
            pattern=search_params.pattern,
            content_search=search_params.content_search,
            path=search_params.path
        )
        
        await audit_logger.log_file_operation(
            operation="search",
            path=search_params.path,
            user_id=current_user.id,
            success=result["success"],
            details={
                "pattern": search_params.pattern,
                "content_search": search_params.content_search,
                "results_count": result.get("count", 0)
            }
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_file_info(
    path: str,
    current_user: User = Depends(get_current_user)
):
    """Get file information."""
    try:
        result = await file_ops.list_directory(path="", pattern=os.path.basename(path))
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        # Find the specific file
        file_info = None
        for file in result["files"]:
            if file["name"] == os.path.basename(path):
                file_info = file
                break
        
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")
        
        return file_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for file operations service."""
    try:
        # Test file operations
        test_result = await file_ops.list_directory(path="")
        
        status = {
            "status": "healthy" if test_result["success"] else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "file_operations",
            "ops_root": str(file_ops.ops_root)
        }
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))