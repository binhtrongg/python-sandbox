"""Pydantic models for request/response validation"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List


class ExecuteRequest(BaseModel):
    """Request to execute Python code"""

    code: str = Field(
        ...,
        description="Python code to execute",
        max_length=50000
    )
    timeout: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum execution time in seconds"
    )

    @field_validator('code')
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        """Validate code is not empty"""
        if not v.strip():
            raise ValueError('Code cannot be empty')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "print('Hello, World!')",
                    "timeout": 10
                }
            ]
        }
    }


class ExecuteResponse(BaseModel):
    """Response with execution result"""

    success: bool = Field(
        ...,
        description="Whether execution was successful"
    )
    stdout: str = Field(
        ...,
        description="Standard output from code execution"
    )
    stderr: str = Field(
        ...,
        description="Standard error from code execution"
    )
    exit_code: int = Field(
        ...,
        description="Exit code from execution (0 = success)"
    )
    execution_time: float = Field(
        ...,
        description="Execution time in seconds"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if execution failed"
    )
    files: List[str] = Field(
        default_factory=list,
        description="URLs of files created during execution"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "stdout": "Hello, World!\n",
                    "stderr": "",
                    "exit_code": 0,
                    "execution_time": 0.234,
                    "error": None,
                    "files": []
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(
        ...,
        description="Service status (healthy/unhealthy)"
    )
    docker_available: bool = Field(
        ...,
        description="Whether Docker is available"
    )
    version: str = Field(
        ...,
        description="Service version"
    )
