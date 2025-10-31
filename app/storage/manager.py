"""Storage manager and factory"""

from typing import Optional
from enum import Enum

from app.storage.base import BaseStorageProvider
from app.storage.r2 import R2StorageProvider
from app.core.exceptions import ExecutionError


class StorageProvider(str, Enum):
    """Available storage providers"""
    R2 = "r2"
    DISABLED = "disabled"


class StorageManager:
    """
    Storage manager for handling file persistence
    
    Provides factory pattern for creating storage providers
    and managing file operations across different backends
    """
    
    def __init__(self, provider_type: str, config: Optional[dict] = None):
        """
        Initialize storage manager
        
        Args:
            provider_type: Type of storage provider ('local', 's3', 'gcs', 'disabled')
            config: Provider-specific configuration
        """
        self.provider_type = provider_type
        self.config = config or {}
        self.provider: Optional[BaseStorageProvider] = None
        
        if provider_type != StorageProvider.DISABLED:
            self.provider = self._create_provider()
    
    def _create_provider(self) -> BaseStorageProvider:
        """Create storage provider based on type"""
        
        if self.provider_type == StorageProvider.R2:
            try:
                return R2StorageProvider(
                    bucket_name=self.config['bucket_name'],
                    account_id=self.config['account_id'],
                    access_key_id=self.config['access_key_id'],
                    secret_access_key=self.config['secret_access_key'],
                    prefix=self.config.get('prefix', 'sandbox'),
                    public_url=self.config.get('public_url')
                )
            except KeyError as e:
                raise ExecutionError(f"Missing R2 configuration: {e}")
        
        else:
            raise ExecutionError(f"Unknown storage provider: {self.provider_type}")
    
    def is_enabled(self) -> bool:
        """Check if storage is enabled"""
        return self.provider is not None
    
    async def save_file(self, file_content: bytes, filename: str, execution_id: str, **kwargs) -> Optional[str]:
        """
        Save file using configured provider
        
        Returns:
            File URL/path if storage enabled, None otherwise
        """
        if not self.is_enabled():
            return None
        
        return await self.provider.save_file(file_content, filename, execution_id, **kwargs)
    
    async def get_file(self, file_path: str) -> bytes:
        """Retrieve file content"""
        if not self.is_enabled():
            raise ExecutionError("Storage is disabled")
        
        return await self.provider.get_file(file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file"""
        if not self.is_enabled():
            return False
        
        return await self.provider.delete_file(file_path)
    
    async def list_files(self, execution_id: str) -> list:
        """List files for execution"""
        if not self.is_enabled():
            return []
        
        return await self.provider.list_files(execution_id)
    
    async def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """Clean up old files"""
        if not self.is_enabled():
            return 0
        
        return await self.provider.cleanup_old_files(max_age_days)
    
    async def health_check(self) -> bool:
        """Check storage health"""
        if not self.is_enabled():
            return True  # Disabled is considered healthy

        return await self.provider.health_check()

    async def generate_presigned_url(self, file_path: str, expiration: int = 18000) -> str:
        """
        Generate a presigned URL for temporary file access

        Args:
            file_path: Path/key to the file
            expiration: URL expiration time in seconds (default: 18000 = 5 hours)

        Returns:
            Presigned URL for downloading the file
        """
        if not self.is_enabled():
            raise ExecutionError("Storage is disabled")

        return await self.provider.generate_presigned_url(file_path, expiration)

    def get_provider_info(self) -> dict:
        """Get provider information"""
        return {
            'provider': self.provider_type,
            'enabled': self.is_enabled(),
            'name': self.provider.get_provider_name() if self.provider else None
        }


# Singleton instance
_storage_manager: Optional[StorageManager] = None


def init_storage_manager(provider_type: str, config: Optional[dict] = None) -> StorageManager:
    """
    Initialize global storage manager
    
    Args:
        provider_type: Storage provider type
        config: Provider configuration
        
    Returns:
        Initialized storage manager
    """
    global _storage_manager
    _storage_manager = StorageManager(provider_type, config)
    return _storage_manager


def get_storage_manager() -> Optional[StorageManager]:
    """
    Get global storage manager instance
    
    Returns:
        Storage manager or None if not initialized
    """
    return _storage_manager
