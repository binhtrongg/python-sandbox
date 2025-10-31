"""Cloudflare R2 storage provider (S3-compatible)"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.storage.base import BaseStorageProvider
from app.core.exceptions import ExecutionError


class R2StorageProvider(BaseStorageProvider):
    """
    Cloudflare R2 storage provider (S3-compatible)
    
    Stores files in R2 with structure:
    bucket/
        prefix/
            executions/
                {execution_id}/
                    file1.csv
    
    R2 is fully S3-compatible and more cost-effective than AWS S3
    """
    
    def __init__(
        self, 
        bucket_name: str,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        prefix: str = "sandbox",
        public_url: Optional[str] = None
    ):
        """
        Initialize R2 storage provider
        
        Args:
            bucket_name: R2 bucket name
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            prefix: Prefix for all files
            public_url: Public URL for R2 bucket (if configured)
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            self.bucket_name = bucket_name
            self.account_id = account_id
            self.prefix = prefix.strip('/')
            self.public_url = public_url.rstrip('/') if public_url else None
            self.ClientError = ClientError
            
            # R2 endpoint URL
            # Format: https://<account_id>.r2.cloudflarestorage.com
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
            
            # Initialize S3 client for R2
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name='auto'  # R2 uses 'auto' region
            )
            
        except ImportError:
            raise ExecutionError(
                "boto3 is required for R2 storage. Install with: pip install boto3"
            )
        except Exception as e:
            raise ExecutionError(f"Failed to initialize R2 client: {e}")
    
    def _get_s3_key(self, execution_id: str, filename: str) -> str:
        """Get R2 key for a file"""
        return f"{self.prefix}/executions/{execution_id}/{filename}"
    
    def _get_public_url(self, key: str) -> Optional[str]:
        """Get public URL for a file if public access is configured"""
        if self.public_url:
            return f"{self.public_url}/{key}"
        return None
    
    async def save_file(
        self, 
        file_content: bytes, 
        filename: str,
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save file to R2
        
        Returns:
            Public URL if configured, otherwise R2 URI (r2://bucket/key)
        """
        try:
            r2_key = self._get_s3_key(execution_id, filename)
            
            # Prepare metadata
            r2_metadata = {
                'execution-id': execution_id,
                'saved-at': datetime.utcnow().isoformat()
            }
            if metadata:
                # R2 metadata keys must be lowercase and alphanumeric
                for key, value in metadata.items():
                    safe_key = key.lower().replace('_', '-')
                    r2_metadata[safe_key] = str(value)
            
            # Upload file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=file_content,
                Metadata=r2_metadata
            )
            
            # Return public URL if available, otherwise R2 URI
            public_url = self._get_public_url(r2_key)
            if public_url:
                return public_url
            
            return f"r2://{self.bucket_name}/{r2_key}"
            
        except self.ClientError as e:
            raise ExecutionError(f"Failed to save file to R2: {e}")
        except Exception as e:
            raise ExecutionError(f"Failed to save file to R2: {e}")
    
    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content from R2"""
        try:
            # Handle r2:// URIs, public URLs, and plain keys
            if file_path.startswith('r2://'):
                # Parse r2://bucket/key
                parts = file_path[5:].split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
            elif file_path.startswith('http://') or file_path.startswith('https://'):
                # Extract key from public URL
                if self.public_url and file_path.startswith(self.public_url):
                    key = file_path[len(self.public_url):].lstrip('/')
                    bucket = self.bucket_name
                else:
                    raise ExecutionError(f"Cannot parse public URL: {file_path}")
            else:
                bucket = self.bucket_name
                key = file_path
            
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
            
        except self.ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in R2: {file_path}")
            raise ExecutionError(f"Failed to retrieve file from R2: {e}")
        except Exception as e:
            raise ExecutionError(f"Failed to retrieve file from R2: {e}")
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from R2"""
        try:
            # Parse r2:// URI, public URL, or use as key
            if file_path.startswith('r2://'):
                parts = file_path[5:].split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
            elif file_path.startswith('http://') or file_path.startswith('https://'):
                # Extract key from public URL
                if self.public_url and file_path.startswith(self.public_url):
                    key = file_path[len(self.public_url):].lstrip('/')
                    bucket = self.bucket_name
                else:
                    return False
            else:
                bucket = self.bucket_name
                key = file_path
            
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            return True
            
        except Exception:
            return False
    
    async def list_files(self, execution_id: str) -> List[str]:
        """List all files for an execution"""
        try:
            prefix = f"{self.prefix}/executions/{execution_id}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Return public URL if available, otherwise R2 URI
                    public_url = self._get_public_url(key)
                    if public_url:
                        files.append(public_url)
                    else:
                        files.append(f"r2://{self.bucket_name}/{key}")
            
            return files
            
        except Exception as e:
            raise ExecutionError(f"Failed to list files from R2: {e}")
    
    async def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """Clean up files older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            prefix = f"{self.prefix}/executions/"
            
            deleted_count = 0
            
            # List all objects under prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' not in page:
                    continue
                
                # Delete old objects
                objects_to_delete = []
                for obj in page['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        objects_to_delete.append({'Key': obj['Key']})
                
                if objects_to_delete:
                    self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
                    deleted_count += len(objects_to_delete)
            
            return deleted_count
            
        except Exception:
            return 0  # Best effort cleanup
    
    def get_provider_name(self) -> str:
        """Get provider name"""
        return "r2"
    
    async def health_check(self) -> bool:
        """Check if R2 is accessible"""
        try:
            # Try to head bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True

        except Exception:
            return False

    async def generate_presigned_url(
        self,
        file_path: str,
        expiration: int = 18000
    ) -> str:
        """
        Generate a presigned URL for temporary file access

        Args:
            file_path: Path/key to the file (r2:// URI, public URL, or key)
            expiration: URL expiration time in seconds (default: 18000 = 5 hours)

        Returns:
            Presigned URL for downloading the file
        """
        try:
            # Parse file_path to extract bucket and key
            if file_path.startswith('r2://'):
                # Parse r2://bucket/key
                parts = file_path[5:].split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
            elif file_path.startswith('http://') or file_path.startswith('https://'):
                # Extract key from public URL
                if self.public_url and file_path.startswith(self.public_url):
                    key = file_path[len(self.public_url):].lstrip('/')
                    bucket = self.bucket_name
                else:
                    raise ExecutionError(f"Cannot parse public URL: {file_path}")
            else:
                # Assume it's a direct key
                bucket = self.bucket_name
                key = file_path

            # Extract filename from key for Content-Disposition header
            filename = key.split('/')[-1]

            # Generate presigned URL using boto3 with Content-Disposition for download
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket,
                    'Key': key,
                    'ResponseContentDisposition': f'attachment; filename="{filename}"'
                },
                ExpiresIn=expiration
            )

            return presigned_url

        except self.ClientError as e:
            raise ExecutionError(f"Failed to generate presigned URL: {e}")
        except Exception as e:
            raise ExecutionError(f"Failed to generate presigned URL: {e}")
