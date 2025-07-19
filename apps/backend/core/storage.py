"""
Storage service for file management and S3 operations
"""
import os
import io
import json
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, BinaryIO
from pathlib import Path
import hashlib
import boto3
from botocore.exceptions import ClientError
from ..core.settings import settings
from ..core.logging import logger


class StorageService:
    """Service for managing file storage and S3 operations"""
    
    def __init__(self):
        self.local_storage_path = Path(settings.LOCAL_STORAGE_PATH) if hasattr(settings, 'LOCAL_STORAGE_PATH') else Path("./storage")
        self.local_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize S3 client if configured
        self.s3_client = None
        self.s3_bucket = None
        
        if hasattr(settings, 'AWS_ACCESS_KEY_ID') and settings.AWS_ACCESS_KEY_ID:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
                )
                self.s3_bucket = getattr(settings, 'S3_BUCKET_NAME', 'brainops-storage')
                logger.info("S3 storage initialized")
            except Exception as e:
                logger.error(f"Failed to initialize S3: {str(e)}")
    
    async def save_file(
        self, 
        file_data: BinaryIO, 
        filename: str, 
        folder: str = "uploads",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Save a file to storage"""
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
            unique_filename = f"{timestamp}_{file_hash}_{filename}"
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
            
            # Save to S3 if available
            if self.s3_client and self.s3_bucket:
                try:
                    key = f"{folder}/{unique_filename}"
                    
                    # Prepare metadata
                    s3_metadata = {
                        'upload_timestamp': timestamp,
                        'original_filename': filename
                    }
                    if metadata:
                        s3_metadata.update({k: str(v) for k, v in metadata.items()})
                    
                    # Upload to S3
                    self.s3_client.put_object(
                        Bucket=self.s3_bucket,
                        Key=key,
                        Body=file_data,
                        ContentType=content_type,
                        Metadata=s3_metadata
                    )
                    
                    # Generate URL
                    url = f"https://{self.s3_bucket}.s3.amazonaws.com/{key}"
                    
                    return {
                        "success": True,
                        "storage_type": "s3",
                        "key": key,
                        "url": url,
                        "filename": unique_filename,
                        "content_type": content_type,
                        "metadata": metadata
                    }
                except Exception as e:
                    logger.error(f"S3 upload failed, falling back to local: {str(e)}")
            
            # Fall back to local storage
            file_path = self.local_storage_path / folder / unique_filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Reset file pointer and save
            file_data.seek(0)
            with open(file_path, 'wb') as f:
                f.write(file_data.read())
            
            # Save metadata
            if metadata:
                metadata_path = file_path.with_suffix('.meta.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
            
            return {
                "success": True,
                "storage_type": "local",
                "path": str(file_path),
                "filename": unique_filename,
                "content_type": content_type,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to save file: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_file(self, key_or_path: str) -> Optional[bytes]:
        """Retrieve a file from storage"""
        try:
            # Try S3 first
            if self.s3_client and self.s3_bucket and "/" in key_or_path:
                try:
                    response = self.s3_client.get_object(
                        Bucket=self.s3_bucket,
                        Key=key_or_path
                    )
                    return response['Body'].read()
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        logger.error(f"S3 retrieval error: {str(e)}")
            
            # Try local storage
            file_path = Path(key_or_path)
            if not file_path.is_absolute():
                file_path = self.local_storage_path / file_path
            
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    return f.read()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get file: {str(e)}")
            return None
    
    async def delete_file(self, key_or_path: str) -> bool:
        """Delete a file from storage"""
        try:
            deleted = False
            
            # Try S3
            if self.s3_client and self.s3_bucket and "/" in key_or_path:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.s3_bucket,
                        Key=key_or_path
                    )
                    deleted = True
                except ClientError as e:
                    logger.error(f"S3 deletion error: {str(e)}")
            
            # Try local
            file_path = Path(key_or_path)
            if not file_path.is_absolute():
                file_path = self.local_storage_path / file_path
            
            if file_path.exists():
                file_path.unlink()
                # Delete metadata if exists
                metadata_path = file_path.with_suffix('.meta.json')
                if metadata_path.exists():
                    metadata_path.unlink()
                deleted = True
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """List files in a folder"""
        files = []
        
        try:
            # List from S3
            if self.s3_client and self.s3_bucket:
                try:
                    paginator = self.s3_client.get_paginator('list_objects_v2')
                    pages = paginator.paginate(
                        Bucket=self.s3_bucket,
                        Prefix=folder,
                        MaxKeys=limit
                    )
                    
                    for page in pages:
                        if 'Contents' in page:
                            for obj in page['Contents']:
                                files.append({
                                    'storage_type': 's3',
                                    'key': obj['Key'],
                                    'size': obj['Size'],
                                    'last_modified': obj['LastModified'].isoformat(),
                                    'url': f"https://{self.s3_bucket}.s3.amazonaws.com/{obj['Key']}"
                                })
                                if len(files) >= limit:
                                    break
                except Exception as e:
                    logger.error(f"S3 listing error: {str(e)}")
            
            # List from local if needed
            if len(files) < limit:
                local_folder = self.local_storage_path / folder
                if local_folder.exists():
                    for file_path in local_folder.iterdir():
                        if file_path.is_file() and not file_path.name.endswith('.meta.json'):
                            stat = file_path.stat()
                            files.append({
                                'storage_type': 'local',
                                'path': str(file_path),
                                'name': file_path.name,
                                'size': stat.st_size,
                                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                            if len(files) >= limit:
                                break
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
        
        return files[:limit]
    
    async def generate_presigned_url(
        self, 
        key: str, 
        expiration: int = 3600,
        operation: str = 'get_object'
    ) -> Optional[str]:
        """Generate a presigned URL for S3 access"""
        if not self.s3_client or not self.s3_bucket:
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                operation,
                Params={'Bucket': self.s3_bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None
    
    async def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copy a file within storage"""
        try:
            # Try S3
            if self.s3_client and self.s3_bucket:
                try:
                    copy_source = {'Bucket': self.s3_bucket, 'Key': source_key}
                    self.s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=self.s3_bucket,
                        Key=dest_key
                    )
                    return True
                except Exception as e:
                    logger.error(f"S3 copy error: {str(e)}")
            
            # Try local
            source_path = Path(source_key)
            if not source_path.is_absolute():
                source_path = self.local_storage_path / source_path
            
            dest_path = Path(dest_key)
            if not dest_path.is_absolute():
                dest_path = self.local_storage_path / dest_path
            
            if source_path.exists():
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(source_path, dest_path)
                
                # Copy metadata if exists
                source_meta = source_path.with_suffix('.meta.json')
                if source_meta.exists():
                    dest_meta = dest_path.with_suffix('.meta.json')
                    shutil.copy2(source_meta, dest_meta)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to copy file: {str(e)}")
            return False
    
    def get_file_info(self, key_or_path: str) -> Optional[Dict[str, Any]]:
        """Get file information without downloading"""
        try:
            # Try S3
            if self.s3_client and self.s3_bucket and "/" in key_or_path:
                try:
                    response = self.s3_client.head_object(
                        Bucket=self.s3_bucket,
                        Key=key_or_path
                    )
                    return {
                        'storage_type': 's3',
                        'key': key_or_path,
                        'size': response['ContentLength'],
                        'content_type': response.get('ContentType'),
                        'last_modified': response['LastModified'].isoformat(),
                        'metadata': response.get('Metadata', {})
                    }
                except ClientError:
                    pass
            
            # Try local
            file_path = Path(key_or_path)
            if not file_path.is_absolute():
                file_path = self.local_storage_path / file_path
            
            if file_path.exists():
                stat = file_path.stat()
                info = {
                    'storage_type': 'local',
                    'path': str(file_path),
                    'name': file_path.name,
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
                # Load metadata if exists
                metadata_path = file_path.with_suffix('.meta.json')
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        info['metadata'] = json.load(f)
                
                return info
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get file info: {str(e)}")
            return None


# Create singleton instance
storage_service = StorageService()


# Convenience functions
async def save_file(*args, **kwargs):
    return await storage_service.save_file(*args, **kwargs)

async def get_file(*args, **kwargs):
    return await storage_service.get_file(*args, **kwargs)

async def delete_file(*args, **kwargs):
    return await storage_service.delete_file(*args, **kwargs)

async def list_files(*args, **kwargs):
    return await storage_service.list_files(*args, **kwargs)

async def generate_presigned_url(*args, **kwargs):
    return await storage_service.generate_presigned_url(*args, **kwargs)