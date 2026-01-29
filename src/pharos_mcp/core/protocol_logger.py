"""
Protocol-level logging for MCP JSON-RPC messages.

Captures all incoming and outgoing MCP protocol messages for debugging
and improvement analysis.
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage
from mcp.types import (
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
)

logger = logging.getLogger(__name__)


class ProtocolLogger:
    """Logs all MCP JSON-RPC protocol messages to a JSON-lines file."""

    def __init__(self, log_dir: Path | None = None, session_id: str | None = None):
        """Initialize the protocol logger.

        Args:
            log_dir: Directory for protocol logs. Defaults to project logs/.
            session_id: Unique identifier for this session.
        """
        if log_dir is None:
            # Check environment variable first
            env_dir = os.environ.get("PHAROS_PROTOCOL_LOG_DIR")
            if env_dir:
                log_dir = Path(env_dir)
            else:
                # Default: logs/ in project root
                project_root = Path(__file__).parent.parent.parent.parent
                log_dir = project_root / "logs"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "protocol.jsonl"
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        """Check if protocol logging is enabled via environment variable."""
        env_value = os.environ.get("PHAROS_PROTOCOL_LOG", "true").lower()
        return env_value in ("true", "1", "yes", "on")

    def _classify_message(self, msg: Any) -> tuple[str, str | None, Any]:
        """Classify a JSON-RPC message and extract key info.

        Args:
            msg: The JSON-RPC message (from SessionMessage.message.root)

        Returns:
            Tuple of (message_type, method, id)
        """
        if isinstance(msg, JSONRPCRequest):
            return "request", msg.method, msg.id
        elif isinstance(msg, JSONRPCResponse):
            return "response", None, msg.id
        elif isinstance(msg, JSONRPCNotification):
            return "notification", msg.method, None
        elif isinstance(msg, JSONRPCError):
            return "error", None, msg.id
        else:
            return "unknown", None, None

    def log_message(
        self,
        direction: str,
        session_message: SessionMessage,
    ) -> None:
        """Log a protocol message.

        Args:
            direction: "incoming" or "outgoing"
            session_message: The SessionMessage to log
        """
        if not self._enabled:
            return

        try:
            msg = session_message.message.root
            message_type, method, msg_id = self._classify_message(msg)

            # Serialize the full payload
            payload = session_message.message.model_dump(
                by_alias=True, exclude_none=True
            )

            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "session_id": self.session_id,
                "direction": direction,
                "message_type": message_type,
            }

            if method:
                entry["method"] = method
            if msg_id is not None:
                entry["id"] = msg_id

            entry["payload"] = payload

            self._write_entry(entry)

        except Exception as e:
            logger.error(f"Failed to log protocol message: {e}")

    def log_exception(self, direction: str, exc: Exception) -> None:
        """Log an exception that occurred during message processing.

        Args:
            direction: "incoming" or "outgoing"
            exc: The exception that occurred
        """
        if not self._enabled:
            return

        try:
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "session_id": self.session_id,
                "direction": direction,
                "message_type": "exception",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            self._write_entry(entry)
        except Exception as e:
            logger.error(f"Failed to log protocol exception: {e}")

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a log entry to the protocol log file.

        Args:
            entry: Log entry dictionary.
        """
        try:
            with self.log_file.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write protocol log: {e}")


class LoggingReceiveStream:
    """Wrapper around MemoryObjectReceiveStream that logs incoming messages."""

    def __init__(
        self,
        stream: MemoryObjectReceiveStream[SessionMessage | Exception],
        protocol_logger: ProtocolLogger,
    ):
        self._stream = stream
        self._logger = protocol_logger

    async def receive(self) -> SessionMessage | Exception:
        """Receive and log a message from the stream."""
        item = await self._stream.receive()

        if isinstance(item, Exception):
            self._logger.log_exception("incoming", item)
        else:
            self._logger.log_message("incoming", item)

        return item

    def __aiter__(self):
        return self

    async def __anext__(self) -> SessionMessage | Exception:
        try:
            return await self.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration

    async def aclose(self) -> None:
        """Close the underlying stream."""
        await self._stream.aclose()


class LoggingSendStream:
    """Wrapper around MemoryObjectSendStream that logs outgoing messages."""

    def __init__(
        self,
        stream: MemoryObjectSendStream[SessionMessage],
        protocol_logger: ProtocolLogger,
    ):
        self._stream = stream
        self._logger = protocol_logger

    async def send(self, item: SessionMessage) -> None:
        """Log and send a message to the stream."""
        self._logger.log_message("outgoing", item)
        await self._stream.send(item)

    async def aclose(self) -> None:
        """Close the underlying stream."""
        await self._stream.aclose()


@asynccontextmanager
async def logged_stdio_server():
    """Context manager that wraps stdio_server with protocol logging.

    Yields the same (read_stream, write_stream) tuple as stdio_server,
    but with logging wrappers that capture all messages.
    """
    session_id = str(uuid.uuid4())[:8]
    protocol_logger = ProtocolLogger(session_id=session_id)

    if protocol_logger._enabled:
        logger.info(
            f"Protocol logging enabled, session_id={session_id}, "
            f"log_file={protocol_logger.log_file}"
        )

    async with stdio_server() as (read_stream, write_stream):
        logged_read = LoggingReceiveStream(read_stream, protocol_logger)
        logged_write = LoggingSendStream(write_stream, protocol_logger)

        yield logged_read, logged_write


# Global protocol logger instance (for optional external access)
_protocol_logger: ProtocolLogger | None = None


def get_protocol_logger() -> ProtocolLogger:
    """Get the global protocol logger instance.

    Returns:
        The ProtocolLogger singleton instance.
    """
    global _protocol_logger
    if _protocol_logger is None:
        _protocol_logger = ProtocolLogger()
    return _protocol_logger
