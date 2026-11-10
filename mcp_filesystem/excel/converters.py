"""Conversion helpers between Excel and CSV/JSON."""

import csv
from pathlib import Path
from typing import Iterable, List

import anyio


async def write_csv(
    output_path: Path,
    rows: Iterable[Iterable],
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> None:
    """Write rows to a CSV file asynchronously."""

    def _write():
        with output_path.open("w", newline="", encoding=encoding) as f:
            writer = csv.writer(f, delimiter=delimiter)
            for row in rows:
                writer.writerow([_normalize_cell(cell) for cell in row])

    await anyio.to_thread.run_sync(_write)


async def read_csv(
    input_path: Path, delimiter: str = ",", encoding: str = "utf-8"
) -> List[List[str]]:
    """Read a CSV file into a list of rows asynchronously."""

    def _read() -> List[List[str]]:
        with input_path.open("r", newline="", encoding=encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            return [list(row) for row in reader]

    return await anyio.to_thread.run_sync(_read)


def _normalize_cell(cell) -> str:
    """Convert cell value to a CSV friendly string."""
    if cell is None:
        return ""
    return str(cell)
