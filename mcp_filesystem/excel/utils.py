"""Utility helpers for Excel integrations."""

import csv
import io
import json
from typing import Any, Iterable, List, Sequence


def format_size(size_bytes: int) -> str:
    """Format bytes to a readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def normalize_output_format(output_format: str) -> str:
    """Normalize output format string."""
    fmt = (output_format or "array").strip().lower()
    if fmt not in {"markdown", "json", "csv", "array"}:
        return "array"
    return fmt


def _coerce_cell(value: Any) -> str:
    """Convert a cell value to string for text outputs."""
    if value is None:
        return ""
    return str(value)


def _ensure_headers(headers: Sequence[Any], width: int) -> List[str]:
    """Ensure headers exist for markdown/csv outputs."""
    if headers:
        return [_coerce_cell(h) for h in headers]
    width = max(1, width)
    return [f"Column {idx + 1}" for idx in range(width)]


def format_read_result(result: dict, output_format: str) -> str:
    """Format read_excel style result into the requested representation."""
    fmt = normalize_output_format(output_format)
    rows: List[List[Any]] = result.get("rows") or []
    sheet = result.get("sheet") or "Sheet1"
    total_rows = result.get("total_rows")
    returned_rows = result.get("returned_rows", len(rows))
    truncated = result.get("truncated", False)
    path = result.get("path")
    range_requested = result.get("range")

    if fmt == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    if fmt == "array":
        # Return raw array format as JSON for easy cell-level manipulation
        array_result = {
            "path": path,
            "sheet": sheet,
            "rows": rows,
            "total_rows": total_rows,
            "returned_rows": returned_rows,
            "truncated": truncated,
        }
        if range_requested:
            array_result["range"] = range_requested
        return json.dumps(array_result, ensure_ascii=False, indent=2)

    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            writer.writerow([_coerce_cell(cell) for cell in row])
        return buffer.getvalue()

    # Markdown formatting
    if not rows:
        lines: List[str] = [f"## Sheet: {sheet}"]
        if path:
            lines.append(f"Path: {path}")
        if range_requested:
            lines.append(f"Range: {range_requested}")
        lines.append("")
        lines.append("*No data*")
        return "\n".join(lines)

    # Use first row as headers for display, or generate column numbers
    first_row_width = len(rows[0]) if rows else 0
    if rows:
        # Use first row as table headers for markdown display
        table_headers = [_coerce_cell(cell) for cell in rows[0]]
        data_rows = rows[1:]
    else:
        table_headers = [f"Column {idx + 1}" for idx in range(first_row_width)]
        data_rows = rows

    lines: List[str] = [f"## Sheet: {sheet}"]
    if path:
        lines.append(f"Path: {path}")
    if range_requested:
        lines.append(f"Range: {range_requested}")
    lines.append("")

    # Header row
    lines.append("| " + " | ".join(table_headers) + " |")
    lines.append("|" + "|".join(["---"] * len(table_headers)) + "|")

    # Data rows
    for row in data_rows:
        normalized_row = [_coerce_cell(cell) for cell in row]
        # Pad rows that are shorter than headers
        if len(normalized_row) < len(table_headers):
            normalized_row.extend([""] * (len(table_headers) - len(normalized_row)))
        lines.append("| " + " | ".join(normalized_row) + " |")

    # Info line
    if total_rows is not None:
        info = f"Showing {returned_rows} of {total_rows} rows"
        if truncated:
            info += " (truncated)"
        lines.extend(["", f"**Info**: {info}"])

    return "\n".join(lines)


def clean_rows(rows: Iterable[Iterable[Any]]) -> List[List[Any]]:
    """Convert rows to a list of lists with None replaced by empty strings."""
    cleaned: List[List[str]] = []
    for row in rows:
        cleaned.append([_coerce_cell(cell) for cell in row])
    return cleaned
