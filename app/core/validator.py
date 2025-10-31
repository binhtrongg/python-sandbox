"""Code validation for security and correctness"""

import ast
from typing import Tuple, List
from app.config import get_settings
from app.core.exceptions import ValidationError, SecurityError

settings = get_settings()


class CodeValidator:
    """
    Validates Python code for security and correctness

    Simple design with clear extension points for future enhancements
    """

    def __init__(self):
        self.forbidden_imports = settings.FORBIDDEN_IMPORTS
        self.max_code_length = settings.MAX_CODE_LENGTH
        self.max_complexity = settings.MAX_COMPLEXITY

    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate code and return (is_valid, errors)

        Args:
            code: Python code to validate

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []

        # Check 1: Code length
        if len(code) > self.max_code_length:
            errors.append(
                f"Code exceeds maximum length of {self.max_code_length} characters"
            )
            return False, errors

        # Check 2: Syntax validation
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return False, errors
        except Exception as e:
            errors.append(f"Failed to parse code: {str(e)}")
            return False, errors

        # Check 3: Forbidden imports
        forbidden_found = self._check_imports(tree)
        if forbidden_found:
            errors.extend([
                f"Forbidden import: {imp}" for imp in forbidden_found
            ])
            return False, errors

        # Check 4: Dangerous patterns (warnings, not errors)
        warnings = self._check_patterns(tree)
        if warnings:
            errors.extend([f"Warning: {w}" for w in warnings])
            # Warnings don't fail validation

        # Check 5: Complexity
        complexity = self._calculate_complexity(tree)
        if complexity > self.max_complexity:
            errors.append(
                f"Code complexity {complexity} exceeds maximum {self.max_complexity}"
            )
            return False, errors

        # All checks passed
        return True, errors

    def _check_imports(self, tree: ast.AST) -> List[str]:
        """Check for forbidden module imports"""
        forbidden_found = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in self.forbidden_imports:
                        forbidden_found.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in self.forbidden_imports:
                        forbidden_found.append(node.module)

        return forbidden_found

    def _check_patterns(self, tree: ast.AST) -> List[str]:
        """Check for potentially dangerous code patterns"""
        warnings = []

        for node in ast.walk(tree):
            # Detect infinite loops
            if isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    warnings.append("Potential infinite loop detected (while True)")

            # Detect exec/eval usage (in case they sneak through)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                        warnings.append(f"Dangerous builtin usage: {node.func.id}")

        return warnings

    def _calculate_complexity(self, tree: ast.AST) -> int:
        """
        Calculate McCabe cyclomatic complexity

        Complexity = 1 + number of decision points
        Decision points: if, while, for, except, and, or
        """
        complexity = 1  # Base complexity

        for node in ast.walk(tree):
            # Control flow statements
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1

            # Boolean operators
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

            # Comprehensions
            elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
                complexity += len(node.generators)

        return complexity


# Singleton instance
validator = CodeValidator()
