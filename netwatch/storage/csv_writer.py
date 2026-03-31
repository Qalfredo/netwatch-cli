"""Atomic CSV append with auto-header and below_contract computation."""

from __future__ import annotations

import csv
import dataclasses
import os
from pathlib import Path

from netwatch.config import Config
from netwatch.models import CSV_FIELDNAMES, MeasurementRow

_DIR_MODE = 0o700
_FILE_MODE = 0o644


def _ensure_data_dir(data_dir: Path) -> None:
    """Create data directory (and logs/archive sub-dirs) with mode 700."""
    for sub in ("", "logs", "archive"):
        p = data_dir / sub if sub else data_dir
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            os.chmod(p, _DIR_MODE)


def _row_to_dict(row: MeasurementRow) -> dict[str, str]:
    """Convert a :class:`MeasurementRow` to a plain string dict for csv.DictWriter."""
    raw = dataclasses.asdict(row)
    out: dict[str, str] = {}
    for key in CSV_FIELDNAMES:
        val = raw.get(key)
        if val is None:
            out[key] = ""
        elif isinstance(val, bool):
            out[key] = "true" if val else "false"
        else:
            out[key] = str(val)
    return out


def compute_below_contract(row: MeasurementRow, cfg: Config) -> bool:
    """Return True if measured speeds are below the contracted threshold.

    Also returns True when a speed measurement is missing (service was down).
    """
    if row.download_mbps is None or row.upload_mbps is None:
        return True
    threshold = cfg.below_contract_threshold
    down_ok = row.download_mbps >= cfg.contracted_down_mbps * threshold
    up_ok = row.upload_mbps >= cfg.contracted_up_mbps * threshold
    return not (down_ok and up_ok)


def write_row(cfg: Config, row: MeasurementRow) -> None:
    """Append *row* to the measurements CSV.

    Creates the directory and header if they do not yet exist.
    Sets file permissions to 644 on creation.
    Never raises; errors are silently swallowed after attempting the write.
    """
    _ensure_data_dir(cfg.data_dir)
    csv_path = cfg.measurements_csv
    needs_header = not csv_path.exists()

    try:
        with csv_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            if needs_header:
                writer.writeheader()
                os.chmod(csv_path, _FILE_MODE)
            writer.writerow(_row_to_dict(row))
    except OSError:
        pass
