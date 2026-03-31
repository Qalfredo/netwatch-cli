"""Archive old measurement rows: compress to .csv.gz and remove from active file."""

from __future__ import annotations

import csv
import gzip
from datetime import UTC, datetime, timedelta

from netwatch.config import Config
from netwatch.models import CSV_FIELDNAMES
from netwatch.storage import csv_reader


def archive(cfg: Config, older_than_days: int) -> str:
    """Move rows older than *older_than_days* to a compressed archive file.

    Returns a human-readable summary.  Never raises.
    """
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

    rows = csv_reader.load(cfg.measurements_csv)
    if not rows:
        return "No measurements to archive."

    old_rows: list[dict[str, str]] = []
    keep_rows: list[dict[str, str]] = []

    for row in rows:
        ts_raw = row.get("timestamp_utc", "")
        try:
            ts = datetime.fromisoformat(ts_raw.rstrip("Z")).replace(tzinfo=UTC)
            if ts < cutoff:
                old_rows.append(row)
            else:
                keep_rows.append(row)
        except ValueError:
            keep_rows.append(row)  # malformed timestamp → keep

    if not old_rows:
        return f"No rows older than {older_than_days} days found."

    # Write archive file
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    archive_filename = f"measurements_v1_until_{cutoff_str}.csv.gz"
    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cfg.archive_dir / archive_filename

    try:
        with gzip.open(archive_path, "wt", encoding="utf-8", newline="") as gz_fh:
            writer = csv.DictWriter(gz_fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for row in old_rows:
                full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
                full.update({k: v for k, v in row.items() if k in CSV_FIELDNAMES})
                writer.writerow(full)
    except OSError as exc:
        return f"Failed to write archive: {exc}"

    # Rewrite active measurements file with only kept rows
    try:
        with cfg.measurements_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for row in keep_rows:
                full = {k: "" for k in CSV_FIELDNAMES}
                full.update({k: v for k, v in row.items() if k in CSV_FIELDNAMES})
                writer.writerow(full)
    except OSError as exc:
        return f"Archived {len(old_rows)} rows but failed to rewrite active file: {exc}"

    return (
        f"Archived {len(old_rows)} rows (older than {older_than_days} days) "
        f"→ {archive_path}\n"
        f"Retained {len(keep_rows)} rows in active file."
    )
