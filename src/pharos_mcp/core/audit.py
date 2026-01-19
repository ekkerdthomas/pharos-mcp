"""
Audit logging for Pharos MCP.

Logs all tool invocations for compliance and debugging.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs all MCP tool operations to a JSON-lines file."""

    def __init__(self, log_dir: Path | None = None):
        """Initialize the audit logger.

        Args:
            log_dir: Directory for audit logs. Defaults to project logs/.
        """
        if log_dir is None:
            # Default: logs/ in project root
            project_root = Path(__file__).parent.parent.parent.parent
            log_dir = project_root / "logs"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit.jsonl"

    def log_operation(
        self,
        tool: str,
        params: dict[str, Any],
        result_summary: str | None = None,
        success: bool = True,
        error: str | None = None,
        user: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Log a tool operation.

        Args:
            tool: Name of the tool invoked.
            params: Parameters passed to the tool.
            result_summary: Brief summary of the result.
            success: Whether the operation succeeded.
            error: Error message if operation failed.
            user: User identifier (for future use).
            duration_ms: Operation duration in milliseconds.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "params": self._sanitize_params(params),
            "success": success,
        }

        if result_summary:
            entry["result_summary"] = result_summary
        if error:
            entry["error"] = error
        if user:
            entry["user"] = user
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 2)

        self._write_entry(entry)

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive information from parameters.

        Args:
            params: Original parameters.

        Returns:
            Sanitized parameters safe for logging.
        """
        sensitive_keys = {"password", "secret", "token", "key", "credential"}
        sanitized = {}

        for key, value in params.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "... [truncated]"
            else:
                sanitized[key] = value

        return sanitized

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a log entry to the audit file.

        Args:
            entry: Log entry dictionary.
        """
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_recent_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent log entries (newest first).
        """
        if not self.log_file.exists():
            return []

        entries = []
        try:
            with open(self.log_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []

        # Return newest first
        return list(reversed(entries[-limit:]))


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.

    Returns:
        The AuditLogger singleton instance.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_tool_call(tool: str):
    """Decorator to automatically audit tool calls.

    Args:
        tool: Name of the tool being decorated.

    Returns:
        Decorator function.
    """
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            audit = get_audit_logger()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Generate result summary
                if isinstance(result, str):
                    summary = result[:200] if len(result) > 200 else result
                elif isinstance(result, dict):
                    summary = f"Dict with keys: {list(result.keys())}"
                elif isinstance(result, list):
                    summary = f"List with {len(result)} items"
                else:
                    summary = str(type(result).__name__)

                audit.log_operation(
                    tool=tool,
                    params=kwargs,
                    result_summary=summary,
                    success=True,
                    duration_ms=duration_ms,
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                audit.log_operation(
                    tool=tool,
                    params=kwargs,
                    success=False,
                    error=str(e),
                    duration_ms=duration_ms,
                )
                raise

        return wrapper
    return decorator
