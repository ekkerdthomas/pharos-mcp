"""
Protocol log analyzer for MCP improvement insights.

Analyzes protocol.jsonl to extract patterns, errors, and improvement opportunities.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


class ProtocolAnalyzer:
    """Analyzes MCP protocol logs for improvement insights."""

    def __init__(self, log_file: Path | None = None):
        """Initialize the analyzer.

        Args:
            log_file: Path to protocol.jsonl. Defaults to project logs/.
        """
        if log_file is None:
            project_root = Path(__file__).parent.parent.parent.parent
            log_file = project_root / "logs" / "protocol.jsonl"
        self.log_file = log_file

    def load_entries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load log entries from the protocol log.

        Args:
            limit: Maximum number of entries to load (most recent). None for all.

        Returns:
            List of log entries, newest first.
        """
        if not self.log_file.exists():
            return []

        entries = []
        with self.log_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Return newest first
        entries.reverse()
        if limit:
            entries = entries[:limit]
        return entries

    def get_tool_calls(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get all tools/call requests with their responses.

        Args:
            limit: Maximum number of tool calls to return.

        Returns:
            List of tool call records with request and response info.
        """
        entries = self.load_entries()

        # Index responses by id
        responses_by_id: dict[Any, dict] = {}
        for entry in entries:
            if entry.get("message_type") == "response" and entry.get("id"):
                responses_by_id[entry["id"]] = entry

        # Match requests with responses
        tool_calls = []
        for entry in entries:
            if (entry.get("message_type") == "request" and
                entry.get("method") == "tools/call"):

                payload = entry.get("payload", {})
                params = payload.get("params", {})

                call = {
                    "timestamp": entry.get("timestamp"),
                    "session_id": entry.get("session_id"),
                    "request_id": entry.get("id"),
                    "tool_name": params.get("name"),
                    "arguments": params.get("arguments", {}),
                }

                # Find matching response
                response = responses_by_id.get(entry.get("id"))
                if response:
                    result = response.get("payload", {}).get("result", {})
                    error = response.get("payload", {}).get("error")
                    call["has_response"] = True
                    call["is_error"] = error is not None
                    call["error"] = error
                    # Truncate large results for summary
                    if isinstance(result, dict) and "content" in result:
                        content = result.get("content", [])
                        if content and isinstance(content, list):
                            text = content[0].get("text", "")
                            call["result_preview"] = text[:500] if len(text) > 500 else text
                            call["result_length"] = len(text)
                else:
                    call["has_response"] = False
                    call["is_error"] = None

                tool_calls.append(call)
                if limit and len(tool_calls) >= limit:
                    break

        return tool_calls

    def get_tool_usage_stats(self) -> dict[str, Any]:
        """Get statistics about tool usage.

        Returns:
            Dictionary with usage stats per tool.
        """
        tool_calls = self.get_tool_calls()

        stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "errors": 0,
            "no_response": 0,
            "common_args": Counter(),
        })

        for call in tool_calls:
            tool_name = call.get("tool_name", "unknown")
            stats[tool_name]["count"] += 1

            if call.get("is_error"):
                stats[tool_name]["errors"] += 1
            if not call.get("has_response"):
                stats[tool_name]["no_response"] += 1

            # Track common argument patterns
            for arg_name in call.get("arguments", {}).keys():
                stats[tool_name]["common_args"][arg_name] += 1

        # Convert to regular dict and Counter to list
        result = {}
        for tool_name, tool_stats in stats.items():
            result[tool_name] = {
                "count": tool_stats["count"],
                "errors": tool_stats["errors"],
                "error_rate": tool_stats["errors"] / tool_stats["count"] if tool_stats["count"] > 0 else 0,
                "no_response": tool_stats["no_response"],
                "common_args": dict(tool_stats["common_args"].most_common(10)),
            }

        return dict(sorted(result.items(), key=lambda x: x[1]["count"], reverse=True))

    def get_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent errors from the protocol log.

        Args:
            limit: Maximum number of errors to return.

        Returns:
            List of error records.
        """
        entries = self.load_entries()

        errors = []
        for entry in entries:
            # Check for error responses
            if entry.get("message_type") == "error":
                errors.append(entry)
            elif entry.get("message_type") == "response":
                payload = entry.get("payload", {})
                if "error" in payload:
                    errors.append({
                        "timestamp": entry.get("timestamp"),
                        "session_id": entry.get("session_id"),
                        "id": entry.get("id"),
                        "error": payload.get("error"),
                    })

            if len(errors) >= limit:
                break

        return errors

    def get_sessions(self) -> list[dict[str, Any]]:
        """Get summary of all sessions in the log.

        Returns:
            List of session summaries.
        """
        entries = self.load_entries()

        sessions: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "message_count": 0,
            "tool_calls": 0,
            "errors": 0,
            "first_seen": None,
            "last_seen": None,
            "methods": Counter(),
        })

        for entry in entries:
            session_id = entry.get("session_id", "unknown")
            timestamp = entry.get("timestamp")

            sessions[session_id]["message_count"] += 1

            if timestamp:
                if sessions[session_id]["first_seen"] is None:
                    sessions[session_id]["first_seen"] = timestamp
                sessions[session_id]["last_seen"] = timestamp

            method = entry.get("method")
            if method:
                sessions[session_id]["methods"][method] += 1
                if method == "tools/call":
                    sessions[session_id]["tool_calls"] += 1

            if entry.get("message_type") == "error" or entry.get("is_error"):
                sessions[session_id]["errors"] += 1

        # Convert to list format
        result = []
        for session_id, data in sessions.items():
            result.append({
                "session_id": session_id,
                "message_count": data["message_count"],
                "tool_calls": data["tool_calls"],
                "errors": data["errors"],
                "first_seen": data["last_seen"],  # Reversed due to newest-first loading
                "last_seen": data["first_seen"],
                "methods": dict(data["methods"].most_common(10)),
            })

        return sorted(result, key=lambda x: x.get("last_seen") or "", reverse=True)

    def generate_improvement_report(self) -> str:
        """Generate a markdown report with improvement insights.

        Returns:
            Markdown-formatted improvement report.
        """
        lines = ["# Protocol Analysis Report", ""]

        # Session summary
        sessions = self.get_sessions()
        lines.append(f"## Sessions: {len(sessions)}")
        total_messages = sum(s["message_count"] for s in sessions)
        total_tool_calls = sum(s["tool_calls"] for s in sessions)
        total_errors = sum(s["errors"] for s in sessions)
        lines.append(f"- Total messages: {total_messages}")
        lines.append(f"- Total tool calls: {total_tool_calls}")
        lines.append(f"- Total errors: {total_errors}")
        lines.append("")

        # Tool usage stats
        stats = self.get_tool_usage_stats()
        if stats:
            lines.append("## Tool Usage")
            lines.append("")
            lines.append("| Tool | Calls | Errors | Error Rate |")
            lines.append("|------|-------|--------|------------|")
            for tool_name, tool_stats in stats.items():
                error_rate = f"{tool_stats['error_rate']:.1%}"
                lines.append(f"| {tool_name} | {tool_stats['count']} | {tool_stats['errors']} | {error_rate} |")
            lines.append("")

        # Recent errors
        errors = self.get_errors(limit=10)
        if errors:
            lines.append("## Recent Errors")
            lines.append("")
            for error in errors[:10]:
                timestamp = error.get("timestamp", "")[:19]
                error_info = error.get("error", {})
                if isinstance(error_info, dict):
                    message = error_info.get("message", str(error_info))
                else:
                    message = str(error_info)
                lines.append(f"- `{timestamp}`: {message[:100]}")
            lines.append("")

        # Improvement suggestions
        lines.append("## Improvement Opportunities")
        lines.append("")

        # High error rate tools
        high_error_tools = [
            (name, s) for name, s in stats.items()
            if s["error_rate"] > 0.1 and s["count"] >= 3
        ]
        if high_error_tools:
            lines.append("### Tools with High Error Rates (>10%)")
            for tool_name, tool_stats in high_error_tools:
                lines.append(f"- **{tool_name}**: {tool_stats['error_rate']:.1%} error rate ({tool_stats['errors']}/{tool_stats['count']})")
            lines.append("")

        # Unused tools (called but no response)
        no_response_tools = [
            (name, s) for name, s in stats.items()
            if s["no_response"] > 0
        ]
        if no_response_tools:
            lines.append("### Tools with Missing Responses")
            for tool_name, tool_stats in no_response_tools:
                lines.append(f"- **{tool_name}**: {tool_stats['no_response']} calls without response")
            lines.append("")

        return "\n".join(lines)


def analyze_protocol_log() -> str:
    """Convenience function to generate improvement report.

    Returns:
        Markdown-formatted improvement report.
    """
    analyzer = ProtocolAnalyzer()
    return analyzer.generate_improvement_report()
