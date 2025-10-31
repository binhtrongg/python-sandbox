"""Docker-based code executor"""

import docker
import time
import uuid
import tarfile
import io
from typing import Dict, Any, List
from pathlib import Path
from docker.errors import ContainerError, ImageNotFound, APIError

from app.executors.base import BaseExecutor
from app.executors.factory import ExecutorRegistry
from app.core.exceptions import ExecutionError, DockerError
from app.config import get_settings
from app.storage import get_storage_manager

settings = get_settings()


@ExecutorRegistry.register("docker")
class DockerExecutor(BaseExecutor):
    """
    Executes code in isolated Docker containers

    Features:
    - Network isolation
    - Resource limits (CPU, memory, PIDs)
    - Read-only filesystem
    - Security hardening

    Extension Points:
    - Add container pooling for better performance
    - Add output streaming
    - Add file upload/download
    """

    def __init__(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            self.image = settings.DOCKER_IMAGE
            self._verify_image()
        except Exception as e:
            raise DockerError(f"Failed to initialize Docker client: {e}")

    def _verify_image(self) -> None:
        """Verify sandbox image exists"""
        try:
            self.client.images.get(self.image)
        except ImageNotFound:
            raise DockerError(
                f"Sandbox image '{self.image}' not found. "
                f"Please build it first: docker build -t {self.image} sandbox-image/"
            )

    async def execute(self, code: str, timeout: int) -> Dict[str, Any]:
        """
        Execute code in isolated Docker container

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            Dict with execution results including file URLs
        """
        start_time = time.time()
        container = None
        execution_id = str(uuid.uuid4())

        try:
            # Create and run container
            container = self.client.containers.run(
                image=self.image,
                command=["python", "-c", code],

                # Resource limits
                mem_limit=settings.DOCKER_MEMORY,
                memswap_limit=settings.DOCKER_MEMORY_SWAP,
                cpu_quota=settings.DOCKER_CPU_QUOTA,
                cpu_period=settings.DOCKER_CPU_PERIOD,
                pids_limit=settings.DOCKER_PIDS_LIMIT,

                # Security settings
                network_disabled=True,
                read_only=False,  # Allow writing to /tmp/output for file output
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],

                # Execution settings
                detach=True,
                remove=False,  # Manual cleanup for better control
                # Note: /tmp/output is writable for file output
            )

            # Wait for completion with timeout
            result = container.wait(timeout=timeout)

            # Get output
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8')

            # Truncate large outputs
            stdout = self._truncate_output(stdout)
            stderr = self._truncate_output(stderr)

            # Extract and save files from /tmp if storage is enabled
            file_urls = await self._extract_and_save_files(container, execution_id)

            execution_time = time.time() - start_time

            return {
                'success': True,
                'stdout': stdout,
                'stderr': stderr,
                'exit_code': result['StatusCode'],
                'execution_time': round(execution_time, 3),
                'error': None,
                'files': file_urls
            }

        except ContainerError as e:
            # Container exited with non-zero code
            execution_time = time.time() - start_time
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': e.exit_status,
                'execution_time': round(execution_time, 3),
                'error': 'Container error',
                'files': []
            }

        except Exception as e:
            # Timeout or other errors
            execution_time = time.time() - start_time

            # Determine error type
            if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                error_type = 'Execution timeout'
            else:
                error_type = 'Execution failed'

            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'execution_time': round(execution_time, 3),
                'error': error_type,
                'files': []
            }

        finally:
            # Cleanup container
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass  # Best effort cleanup

    async def _extract_and_save_files(self, container, execution_id: str) -> List[str]:
        """
        Extract files from container's /tmp/output directory and save to storage

        Args:
            container: Docker container object
            execution_id: Unique execution identifier

        Returns:
            List of file URLs
        """
        file_urls = []
        storage_manager = get_storage_manager()

        # Skip if storage is not enabled
        if not storage_manager or not storage_manager.is_enabled():
            return file_urls

        try:
            # Get tar archive of /tmp/output directory only
            bits, stat = container.get_archive('/tmp/output')
            
            # Extract tar archive
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)
            
            # Read files from tar with limits
            total_size = 0
            file_count = 0

            with tarfile.open(fileobj=tar_stream, mode='r') as tar:
                for member in tar.getmembers():
                    # Skip directories and special files
                    if not member.isfile():
                        continue

                    # Skip hidden files and system files
                    filename = Path(member.name).name
                    if filename.startswith('.'):
                        continue

                    # Check file count limit
                    if file_count >= settings.MAX_FILE_COUNT:
                        print(f"Warning: File count limit reached ({settings.MAX_FILE_COUNT}), skipping remaining files")
                        break

                    # Check individual file size limit
                    if member.size > settings.MAX_FILE_SIZE:
                        print(f"Warning: File {filename} exceeds size limit ({member.size} > {settings.MAX_FILE_SIZE}), skipping")
                        continue

                    # Check total size limit
                    if total_size + member.size > settings.MAX_TOTAL_SIZE:
                        print(f"Warning: Total size limit reached ({settings.MAX_TOTAL_SIZE}), skipping remaining files")
                        break

                    # Extract file content
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        file_content = file_obj.read()

                        # Skip empty files
                        if len(file_content) == 0:
                            continue

                        file_count += 1
                        total_size += len(file_content)
                        
                        # Save to storage
                        try:
                            file_url = await storage_manager.save_file(
                                file_content=file_content,
                                filename=filename,
                                execution_id=execution_id,
                                metadata={
                                    'size': len(file_content),
                                    'original_path': member.name
                                }
                            )
                            if file_url:
                                # Generate presigned URL with 5-hour expiration
                                presigned_url = await storage_manager.generate_presigned_url(
                                    file_path=file_url,
                                    expiration=18000  # 5 hours in seconds
                                )
                                file_urls.append(presigned_url)
                        except Exception as e:
                            # Log error but continue with other files
                            print(f"Failed to save file {filename}: {e}")
        
        except Exception as e:
            # If extraction fails (e.g., /tmp/output is empty or doesn't exist), just return empty list
            # Don't fail the entire execution
            error_msg = str(e).lower()
            if 'no such file' not in error_msg and 'not found' not in error_msg:
                print(f"Failed to extract files from container: {e}")

        return file_urls

    def _truncate_output(self, output: str) -> str:
        """Truncate output if too large"""
        max_size = settings.MAX_OUTPUT_SIZE

        if len(output) > max_size:
            truncated = output[:max_size]
            truncated += f"\n\n[Output truncated - exceeded {max_size} bytes]"
            return truncated

        return output

    async def health_check(self) -> bool:
        """
        Check if Docker is available and image exists

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check Docker daemon
            self.client.ping()

            # Check sandbox image
            self.client.images.get(self.image)

            return True

        except Exception:
            return False

    def cleanup(self) -> None:
        """Cleanup Docker client"""
        try:
            self.client.close()
        except Exception:
            pass  # Best effort cleanup

    def get_name(self) -> str:
        """Get executor name"""
        return "docker"


# Singleton instance - lazy initialization
_executor_instance = None

def get_executor() -> DockerExecutor:
    """Get singleton executor instance (lazy initialization)"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = DockerExecutor()
    return _executor_instance

# For backward compatibility
executor = None  # Will be initialized on first use
