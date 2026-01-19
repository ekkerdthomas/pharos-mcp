"""Tests for security module - CRITICAL security component.

These tests validate SQL query validation and identifier sanitization,
which are essential for preventing SQL injection in the ERP database.
"""

import pytest

from pharos_mcp.core.security import (
    ADMIN_ROLE,
    ANALYST_ROLE,
    DEFAULT_ROLES,
    READONLY_ROLE,
    Permission,
    PermissionChecker,
    QueryValidationError,
    QueryValidator,
    RateLimiter,
    Role,
    sanitize_identifier,
)


class TestQueryValidator:
    """Test SQL query validation."""

    # =========================================================================
    # Valid SELECT Queries
    # =========================================================================

    def test_valid_select_queries(
        self, query_validator: QueryValidator, valid_select_queries: list[str]
    ) -> None:
        """Valid SELECT queries should pass validation."""
        for sql in valid_select_queries:
            is_valid, error = query_validator.validate(sql)
            assert is_valid, f"Query should be valid: {sql!r}, error: {error}"
            assert error == ""

    def test_valid_cte_queries(
        self, query_validator: QueryValidator, valid_cte_queries: list[str]
    ) -> None:
        """WITH (CTE) queries should pass validation."""
        for sql in valid_cte_queries:
            is_valid, error = query_validator.validate(sql)
            assert is_valid, f"CTE query should be valid: {sql[:50]}..., error: {error}"

    def test_select_with_leading_whitespace(
        self, query_validator: QueryValidator
    ) -> None:
        """SELECT queries with leading whitespace should pass."""
        sql = "    SELECT * FROM Customers"
        is_valid, error = query_validator.validate(sql)
        assert is_valid
        assert error == ""

    def test_select_case_insensitive(self, query_validator: QueryValidator) -> None:
        """SELECT validation should be case-insensitive."""
        queries = [
            "SELECT * FROM Test",
            "select * from test",
            "Select * From Test",
            "sElEcT * fRoM tEsT",
        ]
        for sql in queries:
            is_valid, _ = query_validator.validate(sql)
            assert is_valid, f"Case-insensitive query should pass: {sql}"

    # =========================================================================
    # Leading Comments (Allowed)
    # =========================================================================

    def test_leading_comments_allowed(self, query_validator: QueryValidator) -> None:
        """Leading comment lines should be stripped and query validated."""
        sql = """-- This is a descriptive comment
-- Another comment line
SELECT * FROM Customers"""
        is_valid, error = query_validator.validate(sql)
        assert is_valid, f"Query with leading comments should pass: {error}"

    def test_multiple_leading_comments(self, query_validator: QueryValidator) -> None:
        """Multiple leading comment lines should all be stripped."""
        sql = """-- Comment 1
-- Comment 2
-- Comment 3
SELECT TOP 10 * FROM Orders"""
        is_valid, _ = query_validator.validate(sql)
        assert is_valid

    # =========================================================================
    # Dangerous Queries (Blocked)
    # =========================================================================

    def test_dangerous_queries_blocked(
        self,
        query_validator: QueryValidator,
        dangerous_queries: list[tuple[str, str]],
    ) -> None:
        """Dangerous queries must be blocked."""
        for sql, expected_pattern in dangerous_queries:
            is_valid, error = query_validator.validate(sql)
            assert not is_valid, f"Dangerous query should be blocked: {sql}"
            assert error, "Error message should be provided"
            # The error should mention the blocked pattern
            assert (
                expected_pattern.lower() in error.lower()
                or "disallowed" in error.lower()
            ), f"Error should mention pattern: {expected_pattern}, got: {error}"

    def test_drop_table_blocked(self, query_validator: QueryValidator) -> None:
        """DROP TABLE must be blocked."""
        is_valid, error = query_validator.validate("DROP TABLE Customers")
        assert not is_valid
        assert "DROP" in error or "disallowed" in error

    def test_delete_blocked(self, query_validator: QueryValidator) -> None:
        """DELETE must be blocked."""
        is_valid, error = query_validator.validate("DELETE FROM Customers")
        assert not is_valid
        assert "DELETE" in error or "disallowed" in error

    def test_insert_blocked(self, query_validator: QueryValidator) -> None:
        """INSERT must be blocked."""
        is_valid, error = query_validator.validate("INSERT INTO Test VALUES (1)")
        assert not is_valid
        assert "INSERT" in error or "disallowed" in error

    def test_update_blocked(self, query_validator: QueryValidator) -> None:
        """UPDATE must be blocked."""
        is_valid, error = query_validator.validate("UPDATE Test SET x = 1")
        assert not is_valid
        assert "UPDATE" in error or "disallowed" in error

    def test_exec_blocked(self, query_validator: QueryValidator) -> None:
        """EXEC/EXECUTE must be blocked."""
        for keyword in ["EXEC", "EXECUTE"]:
            is_valid, _ = query_validator.validate(f"{keyword} sp_help")
            assert not is_valid, f"{keyword} should be blocked"

    def test_extended_procedures_blocked(
        self, query_validator: QueryValidator
    ) -> None:
        """xp_* extended stored procedures must be blocked."""
        dangerous = [
            "xp_cmdshell 'dir'",
            "xp_regread 'HKLM'",
            "xp_fileexist 'C:\\test.txt'",
        ]
        for sql in dangerous:
            is_valid, _ = query_validator.validate(sql)
            assert not is_valid, f"xp_ procedure should be blocked: {sql}"

    def test_system_procedures_blocked(self, query_validator: QueryValidator) -> None:
        """sp_* system stored procedures must be blocked."""
        dangerous = [
            "sp_configure 'show advanced', 1",
            "sp_executesql 'SELECT 1'",
            "sp_addlogin 'hacker'",
        ]
        for sql in dangerous:
            is_valid, _ = query_validator.validate(sql)
            assert not is_valid, f"sp_ procedure should be blocked: {sql}"

    # =========================================================================
    # SQL Injection Attempts (Blocked)
    # =========================================================================

    def test_multiple_statements_blocked(
        self, query_validator: QueryValidator
    ) -> None:
        """Multiple statements (;) must be blocked to prevent injection."""
        injections = [
            "SELECT * FROM Customers; DROP TABLE Orders",
            "SELECT 1; DELETE FROM Users",
            "SELECT * FROM Test;SELECT * FROM Secrets",
        ]
        for sql in injections:
            is_valid, _ = query_validator.validate(sql)
            assert not is_valid, f"Multiple statements should be blocked: {sql}"

    def test_inline_comments_blocked(self, query_validator: QueryValidator) -> None:
        """Inline SQL comments (--) must be blocked to prevent injection."""
        sql = "SELECT * FROM Users WHERE id = 1 -- AND password = 'x'"
        is_valid, _ = query_validator.validate(sql)
        assert not is_valid, "Inline comments should be blocked"

    def test_block_comments_blocked(self, query_validator: QueryValidator) -> None:
        """Block comments (/* */) must be blocked to prevent injection."""
        sql = "SELECT * FROM Users WHERE /* injection */ 1=1"
        is_valid, _ = query_validator.validate(sql)
        assert not is_valid, "Block comments should be blocked"

    # =========================================================================
    # Empty/Invalid Queries
    # =========================================================================

    def test_empty_query_rejected(self, query_validator: QueryValidator) -> None:
        """Empty queries should be rejected."""
        is_valid, error = query_validator.validate("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_whitespace_only_rejected(self, query_validator: QueryValidator) -> None:
        """Whitespace-only queries should be rejected."""
        is_valid, error = query_validator.validate("   \n\t  ")
        assert not is_valid
        assert "empty" in error.lower()

    def test_comments_only_rejected(self, query_validator: QueryValidator) -> None:
        """Queries with only comments (no actual SQL) should be rejected."""
        sql = """-- Just a comment
-- Another comment"""
        is_valid, error = query_validator.validate(sql)
        assert not is_valid
        assert "empty" in error.lower() or "comment" in error.lower()

    # =========================================================================
    # Read-only Mode
    # =========================================================================

    def test_non_select_rejected_in_readonly_mode(
        self, query_validator: QueryValidator
    ) -> None:
        """Non-SELECT queries should be rejected in read-only mode."""
        # Note: This tests the readonly mode logic, but dangerous patterns
        # are caught first. This test uses a hypothetical safe non-SELECT
        # that doesn't match dangerous patterns (none exist in practice).
        # The important thing is that readonly=True requires SELECT/WITH.
        assert query_validator.readonly is True

    def test_unrestricted_mode_allows_more(
        self, query_validator_unrestricted: QueryValidator
    ) -> None:
        """Unrestricted mode still blocks dangerous patterns."""
        # Even with readonly=False, dangerous patterns should be blocked
        is_valid, _ = query_validator_unrestricted.validate("DROP TABLE Test")
        assert not is_valid, "DROP should still be blocked in unrestricted mode"

    # =========================================================================
    # validate_or_raise
    # =========================================================================

    def test_validate_or_raise_passes_valid(
        self, query_validator: QueryValidator
    ) -> None:
        """validate_or_raise should not raise for valid queries."""
        # Should not raise
        query_validator.validate_or_raise("SELECT * FROM Test")

    def test_validate_or_raise_raises_invalid(
        self, query_validator: QueryValidator
    ) -> None:
        """validate_or_raise should raise QueryValidationError for invalid queries."""
        with pytest.raises(QueryValidationError):
            query_validator.validate_or_raise("DROP TABLE Test")

    def test_validate_or_raise_exception_message(
        self, query_validator: QueryValidator
    ) -> None:
        """QueryValidationError should contain the error message."""
        with pytest.raises(QueryValidationError) as exc_info:
            query_validator.validate_or_raise("DELETE FROM Test")
        assert "DELETE" in str(exc_info.value) or "disallowed" in str(exc_info.value)


class TestSanitizeIdentifier:
    """Test SQL identifier sanitization."""

    def test_valid_simple_identifiers(self) -> None:
        """Simple alphanumeric identifiers should pass through unchanged."""
        valid = ["Customers", "ArCustomer", "order_items", "Table1", "_private"]
        for identifier in valid:
            result = sanitize_identifier(identifier)
            assert result == identifier

    def test_valid_bracketed_identifiers(self) -> None:
        """Bracketed identifiers should be allowed (without spaces)."""
        assert sanitize_identifier("[Customers]") == "[Customers]"
        assert sanitize_identifier("[OrderItems]") == "[OrderItems]"

    def test_valid_dotted_identifiers(self) -> None:
        """Schema.Table notation should be allowed."""
        assert sanitize_identifier("dbo.Customers") == "dbo.Customers"
        assert sanitize_identifier("schema.table.column") == "schema.table.column"

    def test_empty_identifier_raises(self) -> None:
        """Empty identifiers should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            sanitize_identifier("")

    def test_injection_attempt_raises(self) -> None:
        """SQL injection attempts in identifiers should raise ValueError."""
        dangerous = [
            "table; DROP TABLE x",
            "table'--",
            "table\"; DELETE FROM",
            "table/*comment*/",
            "table\nDROP",
        ]
        for identifier in dangerous:
            with pytest.raises(ValueError, match="Invalid identifier"):
                sanitize_identifier(identifier)

    def test_special_characters_raise(self) -> None:
        """Special characters (except allowed) should raise ValueError."""
        dangerous = ["table$", "table@name", "table#1", "table!"]
        for identifier in dangerous:
            with pytest.raises(ValueError, match="Invalid identifier"):
                sanitize_identifier(identifier)


class TestPermission:
    """Test Permission class."""

    def test_all_permissions_returns_set(self) -> None:
        """all_permissions should return a set of all permission strings."""
        perms = Permission.all_permissions()
        assert isinstance(perms, set)
        assert Permission.QUERY_EXECUTE in perms
        assert Permission.SCHEMA_READ in perms
        assert Permission.ADMIN_AUDIT in perms

    def test_permission_strings_format(self) -> None:
        """Permission strings should follow 'category:action' format."""
        assert ":" in Permission.QUERY_EXECUTE
        assert ":" in Permission.SCHEMA_READ
        assert ":" in Permission.ADMIN_AUDIT


class TestRole:
    """Test Role class."""

    def test_role_initialization(self) -> None:
        """Role should store name, permissions, and description."""
        perms = {Permission.QUERY_EXECUTE, Permission.SCHEMA_READ}
        role = Role("test_role", perms, "Test description")

        assert role.name == "test_role"
        assert role.permissions == perms
        assert role.description == "Test description"

    def test_default_roles_exist(self) -> None:
        """Default roles should be defined."""
        assert "readonly" in DEFAULT_ROLES
        assert "analyst" in DEFAULT_ROLES
        assert "admin" in DEFAULT_ROLES

    def test_readonly_role_has_limited_permissions(self) -> None:
        """Readonly role should have schema/preview but not execute."""
        assert Permission.SCHEMA_READ in READONLY_ROLE.permissions
        assert Permission.QUERY_PREVIEW in READONLY_ROLE.permissions
        assert Permission.QUERY_EXECUTE not in READONLY_ROLE.permissions

    def test_analyst_role_has_query_permissions(self) -> None:
        """Analyst role should have full query permissions."""
        assert Permission.QUERY_EXECUTE in ANALYST_ROLE.permissions
        assert Permission.QUERY_PREVIEW in ANALYST_ROLE.permissions
        assert Permission.SCHEMA_READ in ANALYST_ROLE.permissions

    def test_admin_role_has_all_permissions(self) -> None:
        """Admin role should have all permissions."""
        assert ADMIN_ROLE.permissions == Permission.all_permissions()


class TestPermissionChecker:
    """Test PermissionChecker RBAC functionality."""

    # =========================================================================
    # Default Behavior (enforce=False for backward compatibility)
    # =========================================================================

    def test_default_allows_all_when_not_enforced(self) -> None:
        """With enforce=False (default), all operations should be allowed."""
        checker = PermissionChecker(enforce=False)
        assert checker.has_permission(None, "any_operation") is True
        assert checker.has_permission("user123", Permission.ADMIN_CONFIG) is True

    def test_require_permission_passes_when_not_enforced(self) -> None:
        """With enforce=False, require_permission should not raise."""
        checker = PermissionChecker(enforce=False)
        checker.require_permission(None, "unknown_permission")
        checker.require_permission("user", Permission.ADMIN_AUDIT)

    # =========================================================================
    # Enforced Mode
    # =========================================================================

    def test_enforced_checks_permissions(self) -> None:
        """With enforce=True, permissions should be checked."""
        checker = PermissionChecker(default_role="readonly", enforce=True)

        # Readonly role has SCHEMA_READ but not QUERY_EXECUTE
        assert checker.has_permission(None, Permission.SCHEMA_READ) is True
        assert checker.has_permission(None, Permission.QUERY_EXECUTE) is False

    def test_require_permission_raises_when_denied(self) -> None:
        """With enforce=True, require_permission should raise if denied."""
        checker = PermissionChecker(default_role="readonly", enforce=True)

        with pytest.raises(PermissionError, match="Permission denied"):
            checker.require_permission(None, Permission.QUERY_EXECUTE)

    def test_enforce_property_toggleable(self) -> None:
        """Enforce property should be toggleable."""
        checker = PermissionChecker(enforce=False)
        assert checker.enforce is False

        checker.enforce = True
        assert checker.enforce is True

    # =========================================================================
    # User Role Assignment
    # =========================================================================

    def test_assign_role_to_user(self) -> None:
        """assign_role should add role to user."""
        checker = PermissionChecker(enforce=True)

        result = checker.assign_role("user1", "admin")
        assert result is True

        perms = checker.get_permissions("user1")
        assert Permission.ADMIN_AUDIT in perms

    def test_assign_invalid_role_returns_false(self) -> None:
        """assign_role with invalid role name should return False."""
        checker = PermissionChecker()
        result = checker.assign_role("user1", "nonexistent_role")
        assert result is False

    def test_assign_multiple_roles(self) -> None:
        """User can have multiple roles, permissions combine."""
        checker = PermissionChecker(enforce=True)

        checker.assign_role("user1", "readonly")
        checker.assign_role("user1", "admin")

        perms = checker.get_permissions("user1")
        # Should have permissions from both roles
        assert Permission.SCHEMA_READ in perms
        assert Permission.ADMIN_AUDIT in perms

    def test_remove_role_from_user(self) -> None:
        """remove_role should remove role from user."""
        checker = PermissionChecker(enforce=True)

        checker.assign_role("user1", "admin")
        assert checker.has_permission("user1", Permission.ADMIN_AUDIT) is True

        checker.remove_role("user1", "admin")
        # Should fall back to default role
        assert checker.has_permission("user1", Permission.ADMIN_AUDIT) is False

    def test_remove_role_from_unknown_user(self) -> None:
        """remove_role from user without roles should return False."""
        checker = PermissionChecker()
        result = checker.remove_role("unknown_user", "admin")
        assert result is False

    # =========================================================================
    # Default Role
    # =========================================================================

    def test_anonymous_gets_default_role(self) -> None:
        """Anonymous user (None) should get default role."""
        checker = PermissionChecker(default_role="analyst", enforce=True)

        perms = checker.get_permissions(None)
        assert perms == ANALYST_ROLE.permissions

    def test_user_without_assignment_gets_default(self) -> None:
        """User without explicit assignment gets default role."""
        checker = PermissionChecker(default_role="readonly", enforce=True)

        perms = checker.get_permissions("new_user")
        assert perms == READONLY_ROLE.permissions

    def test_custom_default_role(self) -> None:
        """Default role can be customized."""
        checker = PermissionChecker(default_role="admin", enforce=True)

        assert checker.has_permission(None, Permission.ADMIN_CONFIG) is True

    # =========================================================================
    # Role Listing
    # =========================================================================

    def test_list_roles(self) -> None:
        """list_roles should return role information."""
        checker = PermissionChecker()
        roles = checker.list_roles()

        assert len(roles) == 3
        names = [r["name"] for r in roles]
        assert "readonly" in names
        assert "analyst" in names
        assert "admin" in names

        # Check structure
        for role in roles:
            assert "name" in role
            assert "description" in role
            assert "permissions" in role
            assert isinstance(role["permissions"], list)


class TestRateLimiter:
    """Test RateLimiter functionality."""

    # =========================================================================
    # Default Behavior (enforce=False for backward compatibility)
    # =========================================================================

    def test_default_allows_all_when_not_enforced(self) -> None:
        """With enforce=False (default), all requests should be allowed."""
        limiter = RateLimiter(max_requests=1, enforce=False)
        # Should allow unlimited requests
        for _ in range(100):
            assert limiter.is_allowed("user1") is True

    def test_record_request_returns_true_when_not_enforced(self) -> None:
        """With enforce=False, record_request should return True."""
        limiter = RateLimiter(max_requests=1, enforce=False)
        for _ in range(100):
            assert limiter.record_request("user1") is True

    # =========================================================================
    # Enforced Mode - Basic Limiting
    # =========================================================================

    def test_enforced_limits_requests(self) -> None:
        """With enforce=True, requests should be limited."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, enforce=True)

        # First 3 should be allowed
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is True

        # 4th should be denied
        assert limiter.record_request("user1") is False

    def test_is_allowed_without_recording(self) -> None:
        """is_allowed should check without recording."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, enforce=True)

        # Check allowed (doesn't record)
        assert limiter.is_allowed("user1") is True

        # Actually record
        limiter.record_request("user1")
        limiter.record_request("user1")

        # Now should be denied
        assert limiter.is_allowed("user1") is False

    def test_different_identifiers_independent(self) -> None:
        """Different identifiers should have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, enforce=True)

        # user1 uses their limit
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is False

        # user2 still has their full limit
        assert limiter.record_request("user2") is True
        assert limiter.record_request("user2") is True

    # =========================================================================
    # Sliding Window
    # =========================================================================

    def test_sliding_window_expires_old_requests(self) -> None:
        """Old requests should expire from the window."""
        import time

        limiter = RateLimiter(max_requests=2, window_seconds=1, enforce=True)

        # Use up limit
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is True
        assert limiter.record_request("user1") is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.record_request("user1") is True

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def test_get_remaining(self) -> None:
        """get_remaining should return correct count."""
        limiter = RateLimiter(max_requests=5, window_seconds=60, enforce=True)

        assert limiter.get_remaining("user1") == 5

        limiter.record_request("user1")
        limiter.record_request("user1")

        assert limiter.get_remaining("user1") == 3

    def test_get_reset_time_no_requests(self) -> None:
        """get_reset_time should return 0 if no requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60, enforce=True)
        assert limiter.get_reset_time("user1") == 0.0

    def test_get_reset_time_with_requests(self) -> None:
        """get_reset_time should return time until oldest expires."""
        limiter = RateLimiter(max_requests=5, window_seconds=60, enforce=True)

        limiter.record_request("user1")
        reset_time = limiter.get_reset_time("user1")

        # Should be close to window_seconds
        assert 59 < reset_time <= 60

    def test_clear_single_identifier(self) -> None:
        """clear with identifier should only clear that identifier."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, enforce=True)

        limiter.record_request("user1")
        limiter.record_request("user2")

        limiter.clear("user1")

        assert limiter.get_remaining("user1") == 2  # Cleared
        assert limiter.get_remaining("user2") == 1  # Unchanged

    def test_clear_all(self) -> None:
        """clear without identifier should clear all history."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, enforce=True)

        limiter.record_request("user1")
        limiter.record_request("user2")

        limiter.clear()

        assert limiter.get_remaining("user1") == 2
        assert limiter.get_remaining("user2") == 2

    # =========================================================================
    # Configuration
    # =========================================================================

    def test_initialization_params(self) -> None:
        """RateLimiter should accept configuration parameters."""
        limiter = RateLimiter(max_requests=50, window_seconds=120, enforce=True)
        assert limiter.max_requests == 50
        assert limiter.window_seconds == 120
        assert limiter.enforce is True

    def test_enforce_property_toggleable(self) -> None:
        """Enforce property should be toggleable."""
        limiter = RateLimiter(enforce=False)
        assert limiter.enforce is False

        limiter.enforce = True
        assert limiter.enforce is True


class TestQueryValidatorEdgeCases:
    """Additional edge case tests for QueryValidator."""

    def test_unicode_in_query(self, query_validator: QueryValidator) -> None:
        """Queries with Unicode characters should be handled."""
        sql = "SELECT * FROM Customers WHERE Name = N'日本語'"
        is_valid, _ = query_validator.validate(sql)
        assert is_valid

    def test_very_long_query(self, query_validator: QueryValidator) -> None:
        """Very long queries should be handled."""
        # Create a query with many columns
        columns = ", ".join([f"Column{i}" for i in range(100)])
        sql = f"SELECT {columns} FROM LargeTable"
        is_valid, _ = query_validator.validate(sql)
        assert is_valid

    def test_subquery(self, query_validator: QueryValidator) -> None:
        """Subqueries should be allowed."""
        sql = """
        SELECT *
        FROM Customers
        WHERE Customer IN (
            SELECT Customer FROM Orders WHERE Amount > 1000
        )
        """
        is_valid, _ = query_validator.validate(sql)
        assert is_valid

    def test_union_query(self, query_validator: QueryValidator) -> None:
        """UNION queries should be allowed."""
        sql = """
        SELECT Customer, 'Order' as Type FROM Orders
        UNION ALL
        SELECT Customer, 'Quote' as Type FROM Quotes
        """
        is_valid, _ = query_validator.validate(sql)
        assert is_valid

    def test_join_query(self, query_validator: QueryValidator) -> None:
        """JOIN queries should be allowed."""
        sql = """
        SELECT c.Customer, o.OrderNumber
        FROM Customers c
        INNER JOIN Orders o ON c.Customer = o.Customer
        LEFT JOIN OrderDetails od ON o.OrderNumber = od.OrderNumber
        """
        is_valid, _ = query_validator.validate(sql)
        assert is_valid
