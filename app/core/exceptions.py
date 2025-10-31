"""Custom exceptions for the sandbox service"""


class SandboxException(Exception):
    """Base exception for all sandbox errors"""
    pass


class ValidationError(SandboxException):
    """Raised when code validation fails"""
    pass


class ExecutionError(SandboxException):
    """Raised when code execution fails"""
    pass


class TimeoutError(SandboxException):
    """Raised when execution exceeds timeout"""
    pass


class SecurityError(ValidationError):
    """Raised when security validation fails"""
    pass


class DockerError(ExecutionError):
    """Raised when Docker operation fails"""
    pass
