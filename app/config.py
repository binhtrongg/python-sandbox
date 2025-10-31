"""Application configuration with environment variable support"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Set, Union


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Python Sandbox"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security - Forbidden imports
    FORBIDDEN_IMPORTS: Union[Set[str], str] = {
        'os', 'subprocess', 'socket', 'sys',
        'importlib', 'ctypes', '__builtin__',
        'builtins', 'multiprocessing', 'threading'
    }

    @field_validator('FORBIDDEN_IMPORTS', mode='before')
    @classmethod
    def parse_forbidden_imports(cls, v):
        """Parse FORBIDDEN_IMPORTS from string or set"""
        if isinstance(v, str):
            return {item.strip() for item in v.split(',') if item.strip()}
        return v

    # Code validation
    MAX_CODE_LENGTH: int = 50000  # 50KB
    MAX_COMPLEXITY: int = 20

    # Docker configuration
    DOCKER_IMAGE: str = "python-sandbox:latest"
    DOCKER_TIMEOUT: int = 30  # seconds
    DOCKER_MEMORY: str = "128m"
    DOCKER_MEMORY_SWAP: str = "128m"
    DOCKER_CPU_QUOTA: int = 50000  # 0.5 CPU
    DOCKER_CPU_PERIOD: int = 100000
    DOCKER_PIDS_LIMIT: int = 50

    # Output limits
    MAX_OUTPUT_SIZE: int = 10240  # 10KB

    # File extraction limits
    MAX_FILE_SIZE: int = 10485760  # 10MB per file
    MAX_TOTAL_SIZE: int = 52428800  # 50MB total for all files
    MAX_FILE_COUNT: int = 10  # Maximum number of files to extract

    # Executor configuration
    EXECUTOR_PROVIDER: str = "docker"  # Primary executor provider
    EXECUTOR_FALLBACK_PROVIDERS: str = "docker"  # Comma-separated fallback chain

    # Firecracker executor settings (for future use)
    FIRECRACKER_KERNEL_PATH: str = "/var/firecracker/vmlinux"
    FIRECRACKER_ROOTFS_PATH: str = "/var/firecracker/rootfs.ext4"
    FIRECRACKER_SOCKET_PATH: str = "/tmp/firecracker"
    FIRECRACKER_MEMORY_MB: int = 128
    FIRECRACKER_VCPU_COUNT: int = 1

    # gVisor executor settings (for future use)
    GVISOR_RUNTIME: str = "runsc"
    GVISOR_PLATFORM: str = "ptrace"  # or "kvm"

    # Storage configuration - Cloudflare R2
    STORAGE_ENABLED: bool = False
    STORAGE_PROVIDER: str = "r2"  # 'r2' or 'disabled'
    
    # R2 settings
    STORAGE_R2_BUCKET: str = ""
    STORAGE_R2_ACCOUNT_ID: str = ""
    STORAGE_R2_ACCESS_KEY: str = ""
    STORAGE_R2_SECRET_KEY: str = ""
    STORAGE_R2_PREFIX: str = "sandbox"
    STORAGE_R2_PUBLIC_URL: str = ""  # Optional: public URL for R2 bucket
    
    # Storage cleanup
    STORAGE_CLEANUP_DAYS: int = 7  # Delete files older than this

    # Future extensions (not implemented yet)
    RATE_LIMIT_ENABLED: bool = False
    METRICS_ENABLED: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get singleton instance of settings"""
    return Settings()
