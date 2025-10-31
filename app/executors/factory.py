"""Executor factory with registry pattern

This module implements a clean, extensible factory pattern for executor providers.
New executors can be added by simply registering them with the @ExecutorRegistry.register decorator.

Example:
    @ExecutorRegistry.register("my-executor")
    class MyExecutor(BaseExecutor):
        pass

No need to modify the factory code when adding new providers!
"""

from typing import Optional, Dict, Type, List
from app.executors.base import BaseExecutor
from app.config import get_settings
from app.core.exceptions import ExecutionError


class ExecutorRegistry:
    """
    Self-registering executor registry

    Executors register themselves using the @register decorator.
    This eliminates if-else chains and follows the Open/Closed Principle.

    Example:
        @ExecutorRegistry.register("docker")
        class DockerExecutor(BaseExecutor):
            pass
    """

    _registry: Dict[str, Type[BaseExecutor]] = {}

    @classmethod
    def register(cls, provider: str):
        """
        Decorator to register an executor provider

        Args:
            provider: Provider name (e.g., "docker", "firecracker")

        Returns:
            Decorator function

        Example:
            @ExecutorRegistry.register("docker")
            class DockerExecutor(BaseExecutor):
                pass
        """
        def decorator(executor_class: Type[BaseExecutor]):
            if provider in cls._registry:
                print(f"⚠️  Warning: Overwriting executor provider '{provider}'")

            cls._registry[provider] = executor_class
            print(f"📝 Registered executor provider: {provider} -> {executor_class.__name__}")
            return executor_class

        return decorator

    @classmethod
    def get(cls, provider: str) -> Type[BaseExecutor]:
        """
        Get executor class by provider name

        Args:
            provider: Provider name

        Returns:
            Executor class

        Raises:
            ExecutionError: If provider not found
        """
        if provider not in cls._registry:
            available = ', '.join(cls._registry.keys()) or 'none'
            raise ExecutionError(
                f"Unknown executor provider '{provider}'. "
                f"Available providers: {available}"
            )

        return cls._registry[provider]

    @classmethod
    def list_providers(cls) -> List[str]:
        """
        Get list of all registered providers

        Returns:
            List of provider names
        """
        return sorted(cls._registry.keys())

    @classmethod
    def has_provider(cls, provider: str) -> bool:
        """
        Check if provider is registered

        Args:
            provider: Provider name

        Returns:
            True if provider is registered
        """
        return provider in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers (mainly for testing)"""
        cls._registry.clear()


class ExecutorFactory:
    """
    Factory for creating executor instances

    Uses the ExecutorRegistry to dynamically create executors without if-else chains.
    Implements singleton pattern to cache executor instances.

    Example:
        # Get default executor
        executor = ExecutorFactory.create_executor()

        # Get specific executor
        executor = ExecutorFactory.create_executor("firecracker")

        # Get healthy executor with automatic fallback
        executor = await ExecutorFactory.get_healthy_executor()
    """

    _instances: Dict[str, BaseExecutor] = {}

    @classmethod
    def create_executor(cls, provider: Optional[str] = None) -> BaseExecutor:
        """
        Create executor instance based on provider type

        Args:
            provider: Executor provider name (e.g., "docker", "firecracker")
                     If None, uses settings.EXECUTOR_PROVIDER

        Returns:
            Executor instance

        Raises:
            ExecutionError: If provider is unknown or initialization fails
        """
        settings = get_settings()
        provider_type = provider or settings.EXECUTOR_PROVIDER

        # Return cached instance if available
        if provider_type in cls._instances:
            return cls._instances[provider_type]

        # Get executor class from registry (no if-else!)
        executor_class = ExecutorRegistry.get(provider_type)

        # Create instance
        try:
            executor = executor_class()
            cls._instances[provider_type] = executor
            print(f"✅ Executor initialized: {executor.get_name()} (provider: {provider_type})")
            return executor

        except Exception as e:
            raise ExecutionError(
                f"Failed to initialize executor '{provider_type}': {e}"
            )

    @classmethod
    async def get_healthy_executor(cls) -> BaseExecutor:
        """
        Get a healthy executor with automatic fallback

        Tries the primary provider first, then falls back to fallback providers
        in order until a healthy executor is found.

        Returns:
            Healthy executor instance

        Raises:
            ExecutionError: If no healthy executor is available

        Example:
            executor = await ExecutorFactory.get_healthy_executor()
            # Automatically uses Docker if Firecracker fails
        """
        settings = get_settings()

        # Try primary provider
        primary_provider = settings.EXECUTOR_PROVIDER
        try:
            executor = cls.create_executor(primary_provider)
            if await executor.health_check():
                return executor
            else:
                print(f"⚠️  Primary executor ({primary_provider}) health check failed")
        except Exception as e:
            print(f"⚠️  Primary executor ({primary_provider}) unavailable: {e}")

        # Try fallback providers
        fallback_providers = cls._parse_fallback_providers(
            settings.EXECUTOR_FALLBACK_PROVIDERS
        )

        for provider in fallback_providers:
            # Skip if it's the same as primary (already tried)
            if provider == primary_provider:
                continue

            # Skip if provider not registered
            if not ExecutorRegistry.has_provider(provider):
                print(f"⚠️  Fallback provider '{provider}' not registered, skipping")
                continue

            try:
                executor = cls.create_executor(provider)
                if await executor.health_check():
                    print(f"✅ Using fallback executor: {provider}")
                    return executor
                else:
                    print(f"⚠️  Fallback executor ({provider}) health check failed")
            except Exception as e:
                print(f"⚠️  Fallback executor ({provider}) unavailable: {e}")

        # No healthy executor found
        all_providers = [primary_provider] + fallback_providers
        raise ExecutionError(
            f"No healthy executor available. "
            f"Tried: {', '.join(all_providers)}. "
            f"Registered providers: {', '.join(ExecutorRegistry.list_providers())}"
        )

    @classmethod
    def _parse_fallback_providers(cls, fallback_config) -> List[str]:
        """
        Parse fallback providers from configuration

        Args:
            fallback_config: Can be a string (comma-separated), list, or set

        Returns:
            List of provider names
        """
        if isinstance(fallback_config, str):
            # Parse comma-separated string
            return [p.strip() for p in fallback_config.split(',') if p.strip()]
        elif isinstance(fallback_config, (list, set, tuple)):
            return list(fallback_config)
        else:
            return []

    @classmethod
    def cleanup_all(cls) -> None:
        """
        Cleanup all executor instances

        Called during application shutdown to release resources.
        Safe to call multiple times.
        """
        if not cls._instances:
            print("ℹ️  No executors to clean up")
            return

        for provider, executor in cls._instances.items():
            try:
                print(f"🧹 Cleaning up executor: {provider}")
                executor.cleanup()
            except Exception as e:
                print(f"⚠️  Error cleaning up executor '{provider}': {e}")

        cls._instances.clear()
        print("✅ All executors cleaned up")

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available (registered) executor providers

        Returns:
            List of provider names
        """
        return ExecutorRegistry.list_providers()

    @classmethod
    def get_active_providers(cls) -> List[str]:
        """
        Get list of currently active (initialized) providers

        Returns:
            List of active provider names
        """
        return sorted(cls._instances.keys())


# Convenience functions for easier imports

def get_executor(provider: Optional[str] = None) -> BaseExecutor:
    """
    Get executor instance (convenience function)

    Args:
        provider: Optional provider name (docker, firecracker, gvisor)
                 If None, uses default from settings

    Returns:
        Executor instance

    Example:
        from app.executors.factory import get_executor

        executor = get_executor()  # Uses default from settings
        executor = get_executor("firecracker")  # Specific provider
    """
    return ExecutorFactory.create_executor(provider)


async def get_healthy_executor() -> BaseExecutor:
    """
    Get healthy executor with automatic fallback (convenience function)

    Returns:
        Healthy executor instance

    Example:
        from app.executors.factory import get_healthy_executor

        executor = await get_healthy_executor()
        result = await executor.execute(code, timeout)
    """
    return await ExecutorFactory.get_healthy_executor()
