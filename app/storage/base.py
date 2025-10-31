"""Base storage provider interface"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path


class BaseStorageProvider(ABC):
    """
    Abstract base class for storage providers
    
    Providers handle file persistence from Docker containers
    to various storage backends (local, S3, GCS, Azure, etc.)
    """
    
    @abstractmethod
    async def save_file(
        self, 
        file_content: bytes, 
        filename: str,
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save file content to storage
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            execution_id: Unique execution identifier
            metadata: Optional metadata (mime_type, size, etc.)
            
        Returns:
            URL or path to access the saved file
        """
        pass
    
    @abstractmethod
    async def get_file(self, file_path: str) -> bytes:
        """
        Retrieve file content from storage
        
        Args:
            file_path: Path/key to the file
            
        Returns:
            File content as bytes
        """
        pass
    
    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage
        
        Args:
            file_path: Path/key to the file
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_files(self, execution_id: str) -> List[str]:
        """
        List all files for an execution
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            List of file paths/URLs
        """
        pass
    
    @abstractmethod
    async def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """
        Clean up files older than specified days
        
        Args:
            max_age_days: Maximum file age in days
            
        Returns:
            Number of files deleted
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if storage provider is healthy

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        file_path: str,
        expiration: int = 18000
    ) -> str:
        """
        Generate a presigned URL for temporary file access

        Args:
            file_path: Path/key to the file
            expiration: URL expiration time in seconds (default: 18000 = 5 hours)

        Returns:
            Presigned URL for downloading the file
        """
        pass
