"""Tests for FastAPI endpoints"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns service info"""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert data["status"] == "running"


def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "docker_available" in data
    assert "version" in data


def test_execute_simple_code():
    """Test execution of simple valid code"""
    response = client.post(
        "/execute",
        json={
            "code": "print('hello world')",
            "timeout": 10
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "hello world" in data["stdout"]
    assert data["exit_code"] == 0


def test_execute_math_code():
    """Test execution of mathematical operations"""
    response = client.post(
        "/execute",
        json={
            "code": "result = 2 + 2\nprint(result)",
            "timeout": 10
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "4" in data["stdout"]


def test_execute_with_error():
    """Test execution of code that raises error"""
    response = client.post(
        "/execute",
        json={
            "code": "print(undefined_variable)",
            "timeout": 10
        }
    )

    # Should still return 200 but success=false
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["exit_code"] != 0


def test_validation_failure():
    """Test that forbidden imports are rejected"""
    response = client.post(
        "/execute",
        json={
            "code": "import os\nos.system('ls')",
            "timeout": 10
        }
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Validation failed" in data["error"]


def test_syntax_error():
    """Test that syntax errors are caught"""
    response = client.post(
        "/execute",
        json={
            "code": "print('hello",
            "timeout": 10
        }
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False


def test_empty_code():
    """Test that empty code is rejected"""
    response = client.post(
        "/execute",
        json={
            "code": "   ",
            "timeout": 10
        }
    )

    assert response.status_code == 422  # Validation error


def test_timeout_validation():
    """Test timeout parameter validation"""
    # Test timeout too low
    response = client.post(
        "/execute",
        json={
            "code": "print('test')",
            "timeout": 0
        }
    )
    assert response.status_code == 422

    # Test timeout too high
    response = client.post(
        "/execute",
        json={
            "code": "print('test')",
            "timeout": 100
        }
    )
    assert response.status_code == 422


def test_execute_with_imports():
    """Test execution with allowed imports"""
    response = client.post(
        "/execute",
        json={
            "code": "import math\nprint(math.sqrt(16))",
            "timeout": 10
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "4.0" in data["stdout"]


def test_execute_numpy():
    """Test execution with numpy (if available in sandbox)"""
    response = client.post(
        "/execute",
        json={
            "code": "import numpy as np\nprint(np.array([1,2,3]).sum())",
            "timeout": 10
        }
    )

    # Might fail if Docker not available, but should not crash
    assert response.status_code in [200, 500]
