"""Abstract base class for code executors"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseExecutor(ABC):
    """
    Abstract base for code executors

    Strategy Pattern: Different implementations (Docker, gVisor, Firecracker)
    can be swapped by extending this base class

    Extension Point: Add new executors by implementing this interface
    """

    @abstractmethod
    async def execute(self, code: str, timeout: int) -> Dict[str, Any]:
        """
        Execute code and return result

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            Dict with keys:
                - success: bool
                - stdout: str
                - stderr: str
                - exit_code: int
                - execution_time: float
                - error: Optional[str]

        Raises:
            ExecutionError: If execution fails
            TimeoutError: If execution exceeds timeout
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if executor is available and healthy

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        Cleanup resources

        Called on shutdown or after errors
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get executor implementation name

        Returns:
            Name of the executor (e.g., "docker", "gvisor")
        """
        pass
