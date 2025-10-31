"""Tests for code validator"""

import pytest
from app.core.validator import CodeValidator


def test_valid_code():
    """Test validation of valid Python code"""
    validator = CodeValidator()
    code = "print('hello world')"

    is_valid, errors = validator.validate(code)

    assert is_valid is True
    assert len(errors) == 0


def test_syntax_error():
    """Test detection of syntax errors"""
    validator = CodeValidator()
    code = "print('hello"  # Missing closing quote

    is_valid, errors = validator.validate(code)

    assert is_valid is False
    assert any("Syntax error" in err for err in errors)


def test_forbidden_import():
    """Test detection of forbidden imports"""
    validator = CodeValidator()
    code = "import os\nos.system('ls')"

    is_valid, errors = validator.validate(code)

    assert is_valid is False
    assert any("Forbidden import: os" in err for err in errors)


def test_forbidden_import_from():
    """Test detection of forbidden from imports"""
    validator = CodeValidator()
    code = "from subprocess import call"

    is_valid, errors = validator.validate(code)

    assert is_valid is False
    assert any("Forbidden import: subprocess" in err for err in errors)


def test_infinite_loop_warning():
    """Test detection of infinite loops"""
    validator = CodeValidator()
    code = """
while True:
    pass
"""

    is_valid, errors = validator.validate(code)

    # Should still be valid (warning, not error)
    assert is_valid is True
    assert any("infinite loop" in err.lower() for err in errors)


def test_code_too_long():
    """Test rejection of code that's too long"""
    validator = CodeValidator()
    code = "print('x')\n" * 10000  # Very long code

    is_valid, errors = validator.validate(code)

    assert is_valid is False
    assert any("exceeds maximum length" in err for err in errors)


def test_complexity_check():
    """Test complexity calculation"""
    validator = CodeValidator()

    # Simple code
    simple_code = "x = 1 + 2"
    is_valid, _ = validator.validate(simple_code)
    assert is_valid is True

    # Complex code with many branches
    complex_code = """
def foo(x):
    if x > 10:
        if x > 20:
            if x > 30:
                if x > 40:
                    if x > 50:
                        if x > 60:
                            if x > 70:
                                return True
    return False
"""
    is_valid, errors = validator.validate(complex_code)
    # Might fail due to high complexity
    if not is_valid:
        assert any("complexity" in err.lower() for err in errors)


def test_allowed_imports():
    """Test that allowed imports work"""
    validator = CodeValidator()
    code = """
import math
import json
import random
result = math.sqrt(16)
"""

    is_valid, errors = validator.validate(code)

    assert is_valid is True
