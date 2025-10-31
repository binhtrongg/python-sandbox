"""Execution service - Facade for validation and execution"""

from typing import Dict, Any

from app.core.validator import validator
from app.executors.docker import get_executor
from app.core.exceptions import ValidationError


class ExecutionService:
    """
    Orchestrates code validation and execution

    Facade Pattern: Provides simple interface to complex subsystems
    - Coordinates validator and executor
    - Single entry point for code execution
    - Easy to add cross-cutting concerns (logging, metrics, etc.)

    Extension Points:
    - Add logging
    - Add metrics collection
    - Add caching
    - Add rate limiting
    """

    def __init__(self):
        """Initialize service with validator and executor"""
        self.validator = validator
        self._executor = None

    @property
    def executor(self):
        """Lazy-load executor on first access"""
        if self._executor is None:
            self._executor = get_executor()
        return self._executor

    async def execute_code(self, code: str, timeout: int) -> Dict[str, Any]:
        """
        Validate and execute Python code

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            Dict with execution results:
                - success: bool
                - stdout: str
                - stderr: str
                - exit_code: int
                - execution_time: float
                - error: Optional[str]

        Raises:
            ValidationError: If code validation fails
        """
        # Step 1: Validate code
        is_valid, errors = self.validator.validate(code)

        if not is_valid:
            # Get only error messages (filter out warnings)
            error_msgs = [
                err for err in errors
                if not err.startswith('Warning:')
            ]
            raise ValidationError(
                f"Validation failed: {'; '.join(error_msgs)}"
            )

        # Step 2: Execute code
        result = await self.executor.execute(code, timeout)

        # Step 3: Return result
        # Extension point: Add post-processing here
        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all subsystems

        Returns:
            Dict with health status of each component
        """
        docker_healthy = await self.executor.health_check()

        return {
            'docker': docker_healthy,
            'validator': True,  # Validator has no external dependencies
            'overall': docker_healthy
        }


# Singleton instance
service = ExecutionService()
