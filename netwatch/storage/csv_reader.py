"""CSV reader with date-range filtering and numeric aggregation."""

from __future__ import annotations

import csv
import statistics
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Venezuela Standard Time: UTC-4, no DST.
VET = timezone(timedelta(hours=-4))


def load(csv_path: Path) -> list[dict[str, str]]:
    """Read all rows from *csv_path* as a list of string dicts.

    Returns an empty list if the file does not exist.
    """
    if not csv_path.exists():
        return []
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return [dict(row) for row in reader]
    except OSError:
        return []


def filter_by_days(rows: list[dict[str, str]], since_days: int) -> list[dict[str, str]]:
    """Return rows whose ``timestamp_utc`` is within the last *since_days* days."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    return filter_by_range(rows, cutoff, None)


def filter_by_range(
    rows: list[dict[str, str]],
    start: datetime | None,
    end: datetime | None,
) -> list[dict[str, str]]:
    """Return rows within [*start*, *end*] by ``timestamp_utc``.

    Either bound may be None (open-ended).
    """
    result: list[dict[str, str]] = []
    for row in rows:
        raw = row.get("timestamp_utc", "")
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=UTC)
        except ValueError:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        result.append(row)
    return result


def filter_by_date(rows: list[dict[str, str]], date_str: str) -> list[dict[str, str]]:
    """Return rows whose UTC date matches *date_str* (``YYYY-MM-DD``)."""
    return [r for r in rows if r.get("timestamp_utc", "").startswith(date_str)]


def vet_datetime(row: dict[str, str]) -> datetime | None:
    """Return the VET datetime for a row.

    Uses ``timestamp_vet`` when present; falls back to converting ``timestamp_utc``.
    Returns None on parse failure.
    """
    raw = row.get("timestamp_vet", "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    # Fallback: derive from UTC
    utc_raw = row.get("timestamp_utc", "").strip()
    if utc_raw:
        try:
            return datetime.fromisoformat(utc_raw.rstrip("Z")).replace(tzinfo=UTC).astimezone(VET)
        except ValueError:
            pass
    return None


def filter_by_date_vet(rows: list[dict[str, str]], date_str: str) -> list[dict[str, str]]:
    """Return rows whose VET date matches *date_str* (``YYYY-MM-DD``)."""
    result = []
    for row in rows:
        dt = vet_datetime(row)
        if dt and dt.strftime("%Y-%m-%d") == date_str:
            result.append(row)
    return result


def _parse_float(value: str) -> float | None:
    """Parse a CSV string to float, returning None on blank/invalid."""
    v = value.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _p95(values: list[float]) -> float:
    """Return the 95th-percentile of *values* (nearest-rank)."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, int(len(s) * 0.95) - 1)
    return s[idx]


def aggregate(
    rows: list[dict[str, str]],
    columns: list[str],
) -> dict[str, dict[str, float | None]]:
    """Compute mean, min, max, p95 for each numeric column across *rows*.

    Returns a dict keyed by column name, each value being a dict with
    keys ``mean``, ``min``, ``max``, ``p95``, ``count``.
    """
    result: dict[str, dict[str, Any]] = {}
    for col in columns:
        vals = [f for r in rows if (f := _parse_float(r.get(col, ""))) is not None]
        if vals:
            result[col] = {
                "mean": statistics.mean(vals),
                "min": min(vals),
                "max": max(vals),
                "p95": _p95(vals),
                "count": len(vals),
            }
        else:
            result[col] = {"mean": None, "min": None, "max": None, "p95": None, "count": 0}
    return result


def below_contract_count(rows: list[dict[str, str]]) -> int:
    """Count rows where ``below_contract`` is ``true``."""
    return sum(1 for r in rows if r.get("below_contract", "").lower() == "true")


def failed_count(rows: list[dict[str, str]]) -> int:
    """Count rows where ``error_message`` is non-empty."""
    return sum(1 for r in rows if r.get("error_message", "").strip())


def hourly_averages(
    rows: list[dict[str, str]], column: str
) -> dict[int, float | None]:
    """Return mean of *column* grouped by VET hour-of-day (0–23)."""
    buckets: dict[int, list[float]] = {h: [] for h in range(24)}
    for row in rows:
        val_str = row.get(column, "")
        if not val_str:
            continue
        dt = vet_datetime(row)
        if dt is None:
            continue
        try:
            val = float(val_str)
            buckets[dt.hour].append(val)
        except ValueError:
            continue
    return {h: (statistics.mean(v) if v else None) for h, v in buckets.items()}
