"""
Base classes and utilities for MCP tools.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def format_value(value: Any) -> str:
    """Format a value for display, handling special types.

    Args:
        value: The value to format.

    Returns:
        String representation suitable for display.
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        # Binary data (like SQL Server timestamp) - show as hex or skip
        return "(binary)"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        # Remove trailing zeros for cleaner display
        return str(value).rstrip('0').rstrip('.') if '.' in str(value) else str(value)
    if isinstance(value, float):
        # Handle float precision issues
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def format_table_results(
    rows: list[dict[str, Any]],
    max_column_width: int = 50,
    exclude_binary: bool = True,
) -> str:
    """Format query results as a readable table.

    Args:
        rows: List of row dictionaries.
        max_column_width: Maximum width for columns.
        exclude_binary: If True, exclude columns that only contain binary data.

    Returns:
        Formatted table string.
    """
    if not rows:
        return "No results found."

    # Get column names, optionally filtering out binary-only columns
    all_columns = list(rows[0].keys())

    if exclude_binary:
        # Filter out columns where all values are binary (like timestamp)
        columns = []
        for col in all_columns:
            has_non_binary = any(
                not isinstance(row.get(col), bytes) and row.get(col) is not None
                for row in rows
            )
            # Keep column if it has any non-binary, non-null values
            # or if all values are None (might be useful info)
            if has_non_binary or all(row.get(col) is None for row in rows):
                columns.append(col)
    else:
        columns = all_columns

    if not columns:
        return "No displayable columns found."

    # Calculate column widths using formatted values
    widths = {}
    for col in columns:
        col_values = [format_value(row.get(col)) for row in rows]
        max_val_width = max(len(v) for v in col_values) if col_values else 0
        widths[col] = min(max(len(col), max_val_width), max_column_width)

    # Build header
    header = " | ".join(col.ljust(widths[col])[:widths[col]] for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)

    # Build rows
    formatted_rows = []
    for row in rows:
        formatted_row = " | ".join(
            format_value(row.get(col)).ljust(widths[col])[:widths[col]]
            for col in columns
        )
        formatted_rows.append(formatted_row)

    return "\n".join([header, separator] + formatted_rows)


def truncate_value(value: Any, max_length: int = 100) -> str:
    """Truncate a value for display.

    Args:
        value: Value to truncate.
        max_length: Maximum length.

    Returns:
        Truncated string representation.
    """
    s = str(value) if value is not None else ""
    if len(s) > max_length:
        return s[: max_length - 3] + "..."
    return s


def format_count(count: int) -> str:
    """Format a count with commas.

    Args:
        count: Number to format.

    Returns:
        Formatted string.
    """
    return f"{count:,}"
