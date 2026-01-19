"""
Security utilities for Pharos MCP.

Provides query validation and permission checking.
"""

import re
from typing import Any, ClassVar


class QueryValidationError(Exception):
    """Raised when a query fails validation."""

    pass


class QueryValidator:
    """Validates SQL queries for safety."""

    # Patterns that indicate potentially dangerous operations
    DANGEROUS_PATTERNS: ClassVar[list[str]] = [
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
    # Supports SELECT and WITH (CTEs - Common Table Expressions)
    READONLY_PATTERNS: ClassVar[list[str]] = [
        r"^\s*SELECT\b",
        r"^\s*WITH\b",  # CTEs (Common Table Expressions) are read-only
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


class Permission:
    """Available permissions for RBAC."""

    # Query permissions
    QUERY_EXECUTE = "query:execute"
    QUERY_PREVIEW = "query:preview"

    # Schema permissions
    SCHEMA_READ = "schema:read"
    SCHEMA_SEARCH = "schema:search"

    # Data permissions
    DATA_SEARCH = "data:search"

    # Admin permissions
    ADMIN_AUDIT = "admin:audit"
    ADMIN_CONFIG = "admin:config"

    @classmethod
    def all_permissions(cls) -> set[str]:
        """Get all defined permissions."""
        return {
            cls.QUERY_EXECUTE,
            cls.QUERY_PREVIEW,
            cls.SCHEMA_READ,
            cls.SCHEMA_SEARCH,
            cls.DATA_SEARCH,
            cls.ADMIN_AUDIT,
            cls.ADMIN_CONFIG,
        }


class Role:
    """Role with associated permissions."""

    def __init__(self, name: str, permissions: set[str], description: str = ""):
        """Initialize a role.

        Args:
            name: Role identifier.
            permissions: Set of permission strings.
            description: Human-readable description.
        """
        self.name = name
        self.permissions = permissions
        self.description = description


# Default role definitions
READONLY_ROLE = Role(
    name="readonly",
    permissions={
        Permission.QUERY_PREVIEW,
        Permission.SCHEMA_READ,
        Permission.SCHEMA_SEARCH,
    },
    description="Can view schema and preview data (limited rows)",
)

ANALYST_ROLE = Role(
    name="analyst",
    permissions={
        Permission.QUERY_EXECUTE,
        Permission.QUERY_PREVIEW,
        Permission.SCHEMA_READ,
        Permission.SCHEMA_SEARCH,
        Permission.DATA_SEARCH,
    },
    description="Full read-only query access for data analysis",
)

ADMIN_ROLE = Role(
    name="admin",
    permissions=Permission.all_permissions(),
    description="Full access including audit and configuration",
)

# Role registry
DEFAULT_ROLES: dict[str, Role] = {
    "readonly": READONLY_ROLE,
    "analyst": ANALYST_ROLE,
    "admin": ADMIN_ROLE,
}


class PermissionChecker:
    """Role-based access control for MCP operations.

    Manages user-to-role mappings and permission checks. By default,
    all users get the 'analyst' role for backward compatibility.
    """

    def __init__(self, default_role: str = "analyst", enforce: bool = False):
        """Initialize permission checker.

        Args:
            default_role: Role to use for users without explicit assignment.
            enforce: If True, actually enforce permissions. If False, always allow
                    (for backward compatibility during migration).
        """
        self._user_roles: dict[str, list[Role]] = {}
        self._default_role = DEFAULT_ROLES.get(default_role, ANALYST_ROLE)
        self._enforce = enforce

    @property
    def enforce(self) -> bool:
        """Whether permission enforcement is enabled."""
        return self._enforce

    @enforce.setter
    def enforce(self, value: bool) -> None:
        """Enable or disable permission enforcement."""
        self._enforce = value

    def get_user_roles(self, user: str | None) -> list[Role]:
        """Get roles assigned to a user.

        Args:
            user: User identifier (None for anonymous).

        Returns:
            List of assigned roles.
        """
        if user is None:
            return [self._default_role]
        return self._user_roles.get(user, [self._default_role])

    def get_permissions(self, user: str | None) -> set[str]:
        """Get all permissions for a user.

        Args:
            user: User identifier (None for anonymous).

        Returns:
            Set of granted permissions.
        """
        permissions: set[str] = set()
        for role in self.get_user_roles(user):
            permissions.update(role.permissions)
        return permissions

    def has_permission(self, user: str | None, operation: str) -> bool:
        """Check if user has permission for an operation.

        Args:
            user: User identifier.
            operation: Permission string (e.g., 'query:execute').

        Returns:
            True if permitted. Always True if enforce=False.
        """
        if not self._enforce:
            return True
        return operation in self.get_permissions(user)

    def require_permission(self, user: str | None, operation: str) -> None:
        """Require a permission, raising if denied.

        Args:
            user: User identifier.
            operation: Permission string.

        Raises:
            PermissionError: If permission denied and enforcement is enabled.
        """
        if not self.has_permission(user, operation):
            raise PermissionError(f"Permission denied for operation: {operation}")

    def assign_role(self, user: str, role_name: str) -> bool:
        """Assign a role to a user.

        Args:
            user: User identifier.
            role_name: Name of role to assign.

        Returns:
            True if role was assigned, False if role doesn't exist.
        """
        role = DEFAULT_ROLES.get(role_name)
        if role is None:
            return False

        if user not in self._user_roles:
            self._user_roles[user] = []

        if role not in self._user_roles[user]:
            self._user_roles[user].append(role)

        return True

    def remove_role(self, user: str, role_name: str) -> bool:
        """Remove a role from a user.

        Args:
            user: User identifier.
            role_name: Name of role to remove.

        Returns:
            True if role was removed, False if user didn't have it.
        """
        if user not in self._user_roles:
            return False

        role = DEFAULT_ROLES.get(role_name)
        if role and role in self._user_roles[user]:
            self._user_roles[user].remove(role)
            return True
        return False

    def list_roles(self) -> list[dict[str, Any]]:
        """List all available roles.

        Returns:
            List of role information dictionaries.
        """
        return [
            {
                "name": role.name,
                "description": role.description,
                "permissions": sorted(role.permissions),
            }
            for role in DEFAULT_ROLES.values()
        ]


class RateLimiter:
    """Thread-safe sliding window rate limiter.

    Tracks requests per identifier (user, IP, etc.) and limits
    the number of requests within a configurable time window.
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        enforce: bool = False,
    ):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window.
            window_seconds: Time window in seconds.
            enforce: If True, actually enforce limits. If False, always allow
                    (for backward compatibility during migration).
        """
        import threading

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._enforce = enforce
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @property
    def enforce(self) -> bool:
        """Whether rate limiting enforcement is enabled."""
        return self._enforce

    @enforce.setter
    def enforce(self, value: bool) -> None:
        """Enable or disable rate limiting enforcement."""
        self._enforce = value

    def _cleanup_old_requests(self, identifier: str, now: float) -> None:
        """Remove requests outside the current window.

        Args:
            identifier: Unique identifier.
            now: Current timestamp.
        """
        cutoff = now - self.window_seconds
        if identifier in self._requests:
            self._requests[identifier] = [
                ts for ts in self._requests[identifier] if ts > cutoff
            ]

    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed without recording it.

        Args:
            identifier: Unique identifier for rate limiting.

        Returns:
            True if allowed. Always True if enforce=False.
        """
        if not self._enforce:
            return True

        import time

        now = time.time()

        with self._lock:
            self._cleanup_old_requests(identifier, now)
            current_count = len(self._requests.get(identifier, []))
            return current_count < self.max_requests

    def record_request(self, identifier: str) -> bool:
        """Record a request and return whether it was allowed.

        Args:
            identifier: Unique identifier.

        Returns:
            True if request was recorded and allowed.
            False if rate limit exceeded.
            Always True if enforce=False.
        """
        if not self._enforce:
            return True

        import time

        now = time.time()

        with self._lock:
            self._cleanup_old_requests(identifier, now)

            if identifier not in self._requests:
                self._requests[identifier] = []

            if len(self._requests[identifier]) >= self.max_requests:
                return False

            self._requests[identifier].append(now)
            return True

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests allowed in current window.

        Args:
            identifier: Unique identifier.

        Returns:
            Number of remaining requests allowed.
        """
        import time

        now = time.time()

        with self._lock:
            self._cleanup_old_requests(identifier, now)
            current = len(self._requests.get(identifier, []))
            return max(0, self.max_requests - current)

    def get_reset_time(self, identifier: str) -> float:
        """Get seconds until rate limit resets for identifier.

        Args:
            identifier: Unique identifier.

        Returns:
            Seconds until oldest request expires from window.
            Returns 0.0 if no requests recorded.
        """
        import time

        now = time.time()

        with self._lock:
            self._cleanup_old_requests(identifier, now)
            requests = self._requests.get(identifier, [])

            if not requests:
                return 0.0

            oldest = min(requests)
            return max(0.0, (oldest + self.window_seconds) - now)

    def clear(self, identifier: str | None = None) -> None:
        """Clear request history.

        Args:
            identifier: If provided, clear only that identifier.
                       If None, clear all history.
        """
        with self._lock:
            if identifier is None:
                self._requests.clear()
            elif identifier in self._requests:
                del self._requests[identifier]


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
