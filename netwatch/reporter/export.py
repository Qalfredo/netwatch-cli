"""Filtered CSV export for regulatory/legal submission."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from netwatch.models import CSV_FIELDNAMES
from netwatch.storage import csv_reader


def export_csv(
    csv_path: Path,
    since_days: int = 30,
    until: str | None = None,
) -> str:
    """Return filtered CSV rows as a string.

    *since_days* controls the look-back window.
    *until* (``YYYY-MM-DD``) sets an inclusive upper bound; defaults to today.
    """
    rows = csv_reader.load(csv_path)

    end_dt: datetime | None = None
    if until:
        try:
            end_date = date.fromisoformat(until)
            end_dt = datetime(end_date.year, end_date.month, end_date.day,
                              23, 59, 59, tzinfo=UTC)
        except ValueError:
            pass

    start_dt = datetime.now(UTC) - timedelta(days=since_days)
    filtered = csv_reader.filter_by_range(rows, start_dt, end_dt)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    for row in filtered:
        full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
        full.update({k: v for k, v in row.items() if k in CSV_FIELDNAMES})
        writer.writerow(full)

    return buf.getvalue()


def write_export_file(
    csv_path: Path,
    output_path: Path,
    since_days: int = 30,
    until: str | None = None,
) -> int:
    """Write filtered CSV to *output_path* and return row count."""
    content = export_csv(csv_path, since_days, until)
    rows = content.count("\n") - 1  # subtract header
    output_path.write_text(content, encoding="utf-8")
    return max(rows, 0)
