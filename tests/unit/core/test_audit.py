"""Tests for audit logging module."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pharos_mcp.core.audit import AuditLogger, audit_tool_call


class TestAuditLogger:
    """Test AuditLogger functionality."""

    @pytest.fixture
    def temp_log_dir(self) -> Path:
        """Create a temporary directory for test logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def audit_logger(self, temp_log_dir: Path) -> AuditLogger:
        """Create an AuditLogger with a temp directory."""
        return AuditLogger(log_dir=temp_log_dir)

    # =========================================================================
    # Basic Logging
    # =========================================================================

    def test_log_operation_creates_entry(self, audit_logger: AuditLogger) -> None:
        """log_operation should create a JSON-lines entry."""
        audit_logger.log_operation(
            tool="test_tool",
            params={"param1": "value1"},
            result_summary="Test result",
            success=True,
        )

        assert audit_logger.log_file.exists()
        content = audit_logger.log_file.read_text()
        entry = json.loads(content.strip())

        assert entry["tool"] == "test_tool"
        assert entry["params"] == {"param1": "value1"}
        assert entry["result_summary"] == "Test result"
        assert entry["success"] is True
        assert "timestamp" in entry

    def test_log_operation_with_error(self, audit_logger: AuditLogger) -> None:
        """log_operation should include error message on failure."""
        audit_logger.log_operation(
            tool="failing_tool",
            params={"query": "SELECT *"},
            success=False,
            error="Connection timeout",
        )

        entries = audit_logger.get_recent_entries()
        assert len(entries) == 1
        assert entries[0]["success"] is False
        assert entries[0]["error"] == "Connection timeout"

    def test_log_operation_with_duration(self, audit_logger: AuditLogger) -> None:
        """log_operation should include duration when provided."""
        audit_logger.log_operation(
            tool="timed_tool",
            params={},
            success=True,
            duration_ms=123.456,
        )

        entries = audit_logger.get_recent_entries()
        assert entries[0]["duration_ms"] == 123.46  # Rounded to 2 decimals

    def test_log_operation_with_user(self, audit_logger: AuditLogger) -> None:
        """log_operation should include user when provided."""
        audit_logger.log_operation(
            tool="user_tool",
            params={},
            success=True,
            user="test_user",
        )

        entries = audit_logger.get_recent_entries()
        assert entries[0]["user"] == "test_user"

    # =========================================================================
    # Parameter Sanitization
    # =========================================================================

    def test_sanitize_params_redacts_passwords(
        self, audit_logger: AuditLogger
    ) -> None:
        """Sensitive parameters should be redacted."""
        params = {
            "query": "SELECT *",
            "password": "secret123",
            "api_key": "abc123",
            "db_token": "xyz789",
        }

        sanitized = audit_logger._sanitize_params(params)

        assert sanitized["query"] == "SELECT *"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["db_token"] == "[REDACTED]"

    def test_sanitize_params_case_insensitive(
        self, audit_logger: AuditLogger
    ) -> None:
        """Sensitive key detection should be case-insensitive."""
        params = {
            "PASSWORD": "secret",
            "ApiKey": "key123",
            "DB_SECRET": "shhh",
        }

        sanitized = audit_logger._sanitize_params(params)

        assert sanitized["PASSWORD"] == "[REDACTED]"
        assert sanitized["ApiKey"] == "[REDACTED]"
        assert sanitized["DB_SECRET"] == "[REDACTED]"

    def test_sanitize_params_truncates_long_values(
        self, audit_logger: AuditLogger
    ) -> None:
        """Long string values should be truncated."""
        long_value = "x" * 2000
        params = {"long_param": long_value}

        sanitized = audit_logger._sanitize_params(params)

        assert len(sanitized["long_param"]) < len(long_value)
        assert "[truncated]" in sanitized["long_param"]
        assert sanitized["long_param"].startswith("x" * 1000)

    def test_sanitize_params_preserves_normal_values(
        self, audit_logger: AuditLogger
    ) -> None:
        """Normal parameters should pass through unchanged."""
        params = {
            "table_name": "Customers",
            "limit": 100,
            "columns": ["Name", "Balance"],
        }

        sanitized = audit_logger._sanitize_params(params)

        assert sanitized == params

    # =========================================================================
    # Reading Entries
    # =========================================================================

    def test_get_recent_entries_empty(self, audit_logger: AuditLogger) -> None:
        """get_recent_entries should return empty list if no logs."""
        entries = audit_logger.get_recent_entries()
        assert entries == []

    def test_get_recent_entries_respects_limit(
        self, audit_logger: AuditLogger
    ) -> None:
        """get_recent_entries should respect the limit parameter."""
        # Log 10 entries
        for i in range(10):
            audit_logger.log_operation(
                tool=f"tool_{i}",
                params={},
                success=True,
            )

        entries = audit_logger.get_recent_entries(limit=5)
        assert len(entries) == 5

    def test_get_recent_entries_newest_first(
        self, audit_logger: AuditLogger
    ) -> None:
        """get_recent_entries should return newest entries first."""
        for i in range(5):
            audit_logger.log_operation(
                tool=f"tool_{i}",
                params={},
                success=True,
            )

        entries = audit_logger.get_recent_entries()

        # Newest (tool_4) should be first
        assert entries[0]["tool"] == "tool_4"
        assert entries[-1]["tool"] == "tool_0"

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_log_creates_directory(self, temp_log_dir: Path) -> None:
        """AuditLogger should create log directory if it doesn't exist."""
        nested_dir = temp_log_dir / "nested" / "audit"
        logger = AuditLogger(log_dir=nested_dir)

        assert nested_dir.exists()
        assert logger.log_dir == nested_dir

    def test_multiple_entries_jsonl_format(
        self, audit_logger: AuditLogger
    ) -> None:
        """Multiple entries should be written as JSON-lines."""
        for i in range(3):
            audit_logger.log_operation(tool=f"tool_{i}", params={}, success=True)

        lines = audit_logger.log_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            # Each line should be valid JSON
            entry = json.loads(line)
            assert "tool" in entry
            assert "timestamp" in entry

    def test_optional_fields_omitted_when_none(
        self, audit_logger: AuditLogger
    ) -> None:
        """Optional fields should not appear in log when not provided."""
        audit_logger.log_operation(
            tool="minimal_tool",
            params={},
            success=True,
        )

        entries = audit_logger.get_recent_entries()
        entry = entries[0]

        assert "result_summary" not in entry
        assert "error" not in entry
        assert "user" not in entry
        assert "duration_ms" not in entry


class TestAuditToolCallDecorator:
    """Test the audit_tool_call decorator."""

    @pytest.fixture
    def mock_audit_logger(self) -> AuditLogger:
        """Create a mock audit logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=Path(tmpdir))
            yield logger

    @pytest.mark.asyncio
    async def test_decorator_logs_successful_call(
        self, mock_audit_logger: AuditLogger
    ) -> None:
        """Decorator should log successful tool calls."""
        with patch("pharos_mcp.core.audit.get_audit_logger", return_value=mock_audit_logger):

            @audit_tool_call("test_decorated_tool")
            async def decorated_func(param1: str) -> str:
                return "result"

            result = await decorated_func(param1="value1")

            assert result == "result"

            entries = mock_audit_logger.get_recent_entries()
            assert len(entries) == 1
            assert entries[0]["tool"] == "test_decorated_tool"
            assert entries[0]["success"] is True
            assert "duration_ms" in entries[0]

    @pytest.mark.asyncio
    async def test_decorator_logs_failed_call(
        self, mock_audit_logger: AuditLogger
    ) -> None:
        """Decorator should log failed tool calls with error."""
        with patch("pharos_mcp.core.audit.get_audit_logger", return_value=mock_audit_logger):

            @audit_tool_call("failing_decorated_tool")
            async def failing_func() -> str:
                raise ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                await failing_func()

            entries = mock_audit_logger.get_recent_entries()
            assert len(entries) == 1
            assert entries[0]["tool"] == "failing_decorated_tool"
            assert entries[0]["success"] is False
            assert "Test error" in entries[0]["error"]

    @pytest.mark.asyncio
    async def test_decorator_captures_kwargs(
        self, mock_audit_logger: AuditLogger
    ) -> None:
        """Decorator should capture keyword arguments in params."""
        with patch("pharos_mcp.core.audit.get_audit_logger", return_value=mock_audit_logger):

            @audit_tool_call("kwarg_tool")
            async def kwarg_func(table: str, limit: int = 10) -> str:
                return f"Result for {table}"

            await kwarg_func(table="Customers", limit=50)

            entries = mock_audit_logger.get_recent_entries()
            assert entries[0]["params"]["table"] == "Customers"
            assert entries[0]["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_decorator_generates_result_summary(
        self, mock_audit_logger: AuditLogger
    ) -> None:
        """Decorator should generate appropriate result summaries."""
        with patch("pharos_mcp.core.audit.get_audit_logger", return_value=mock_audit_logger):

            @audit_tool_call("summary_tool")
            async def summary_func(type: str) -> Any:
                if type == "string":
                    return "Short result"
                elif type == "long_string":
                    return "x" * 500
                elif type == "dict":
                    return {"key1": "val1", "key2": "val2"}
                elif type == "list":
                    return [1, 2, 3, 4, 5]
                return None

            # Test string result
            await summary_func(type="string")
            entries = mock_audit_logger.get_recent_entries()
            assert entries[0]["result_summary"] == "Short result"

            # Test long string truncation
            await summary_func(type="long_string")
            entries = mock_audit_logger.get_recent_entries()
            assert len(entries[0]["result_summary"]) <= 200

            # Test dict summary
            await summary_func(type="dict")
            entries = mock_audit_logger.get_recent_entries()
            assert "Dict with keys" in entries[0]["result_summary"]

            # Test list summary
            await summary_func(type="list")
            entries = mock_audit_logger.get_recent_entries()
            assert "5 items" in entries[0]["result_summary"]
