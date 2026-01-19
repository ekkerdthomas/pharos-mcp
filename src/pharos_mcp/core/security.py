"""
Security utilities for Pharos MCP.

Provides query validation and permission checking.
"""

import re
from typing import Any


class QueryValidationError(Exception):
    """Raised when a query fails validation."""

    pass


class QueryValidator:
    """Validates SQL queries for safety."""

    # Patterns that indicate potentially dangerous operations
    DANGEROUS_PATTERNS = [
        r"\bDROP\b",
        r"\bTRUNCATE\b",
        r"\bDELETE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bDENY\b",
        r"\bBACKUP\b",
        r"\bRESTORE\b",
        r"\bSHUTDOWN\b",
        r"\bxp_",  # Extended stored procedures
        r"\bsp_",  # System stored procedures
        r"--",  # SQL comments (potential injection)
        r"/\*",  # Block comments
        r";\s*\w",  # Multiple statements
    ]

    # Allowed query patterns (for read-only mode)
    READONLY_PATTERNS = [
        r"^\s*SELECT\b",
    ]

    def __init__(self, readonly: bool = True, allowed_operations: list[str] | None = None):
        """Initialize the query validator.

        Args:
            readonly: If True, only SELECT queries are allowed.
            allowed_operations: List of allowed SQL operations (e.g., ['SELECT']).
        """
        self.readonly = readonly
        self.allowed_operations = allowed_operations or ["SELECT"]
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        self._dangerous_re = [
            re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS
        ]
        self._readonly_re = [
            re.compile(p, re.IGNORECASE) for p in self.READONLY_PATTERNS
        ]

    def _strip_leading_comments(self, sql: str) -> str:
        """Strip leading comment lines from SQL.

        Removes lines that start with -- at the beginning of the query.
        This allows descriptive comments in query templates while still
        blocking inline comment injection attempts.

        Args:
            sql: SQL query potentially with leading comments.

        Returns:
            SQL with leading comment lines removed.
        """
        lines = sql.strip().split('\n')
        # Skip lines that are pure comments (start with --)
        while lines and lines[0].strip().startswith('--'):
            lines.pop(0)
        return '\n'.join(lines).strip()

    def validate(self, sql: str) -> tuple[bool, str]:
        """Validate a SQL query.

        Args:
            sql: SQL query to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not sql or not sql.strip():
            return False, "Query cannot be empty"

        # Strip leading comment lines (allowed for descriptive purposes)
        # but validate the actual SQL for injection attempts
        sql_normalized = self._strip_leading_comments(sql)

        if not sql_normalized:
            return False, "Query cannot be empty (only comments provided)"

        # Check for dangerous patterns in the actual SQL (after stripping leading comments)
        for pattern in self._dangerous_re:
            if pattern.search(sql_normalized):
                match = pattern.pattern.replace(r"\b", "").replace("\\", "")
                return False, f"Query contains disallowed pattern: {match}"

        # In readonly mode, ensure query starts with SELECT
        if self.readonly:
            is_select = any(p.match(sql_normalized) for p in self._readonly_re)
            if not is_select:
                return False, "Only SELECT queries are allowed in read-only mode"

        return True, ""

    def validate_or_raise(self, sql: str) -> None:
        """Validate a SQL query, raising an exception if invalid.

        Args:
            sql: SQL query to validate.

        Raises:
            QueryValidationError: If query fails validation.
        """
        is_valid, error = self.validate(sql)
        if not is_valid:
            raise QueryValidationError(error)


class PermissionChecker:
    """Stub for future role-based access control.

    Currently allows all operations - will be expanded in Phase 2+.
    """

    def __init__(self):
        """Initialize permission checker."""
        self._permissions: dict[str, list[str]] = {}

    def has_permission(self, user: str | None, operation: str) -> bool:
        """Check if a user has permission for an operation.

        Args:
            user: User identifier (None for anonymous).
            operation: Operation being attempted.

        Returns:
            True if permitted (currently always True).
        """
        # Phase 1: Allow all operations
        return True

    def require_permission(self, user: str | None, operation: str) -> None:
        """Require a permission, raising if not granted.

        Args:
            user: User identifier.
            operation: Operation being attempted.

        Raises:
            PermissionError: If permission denied.
        """
        if not self.has_permission(user, operation):
            raise PermissionError(f"Permission denied for operation: {operation}")


class RateLimiter:
    """Stub for future rate limiting.

    Currently does not limit - will be expanded in Phase 2+.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window.
            window_seconds: Time window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed.

        Args:
            identifier: Unique identifier for rate limiting.

        Returns:
            True if allowed (currently always True).
        """
        # Phase 1: No rate limiting
        return True

    def record_request(self, identifier: str) -> None:
        """Record a request for rate limiting.

        Args:
            identifier: Unique identifier.
        """
        # Phase 1: No-op
        pass


def sanitize_identifier(identifier: str) -> str:
    """Sanitize a SQL identifier (table name, column name).

    Args:
        identifier: The identifier to sanitize.

    Returns:
        Sanitized identifier safe for use in queries.

    Raises:
        ValueError: If identifier contains invalid characters.
    """
    # Remove or escape dangerous characters
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # Allow only alphanumeric, underscore, and brackets
    if not re.match(r"^[\w\[\]\.]+$", identifier):
        raise ValueError(f"Invalid identifier: {identifier}")

    return identifier
