"""Unit tests for netwatch.archiver."""

from __future__ import annotations

import csv
import gzip
from datetime import UTC, datetime, timedelta
from pathlib import Path

from netwatch.archiver import archive
from netwatch.config import load_config
from netwatch.models import CSV_FIELDNAMES


def _cfg(tmp_path: Path):  # type: ignore[no-untyped-def]
    p = tmp_path / "config.toml"
    p.write_text(
        f'[netwatch]\ndata_dir = "{tmp_path / "data"}"\n', encoding="utf-8"
    )
    return load_config(p)


def _ts(days_ago: int) -> str:
    dt = datetime.now(UTC) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
            full.update(row)
            writer.writerow(full)


class TestArchive:
    def test_empty_file_returns_message(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        result = archive(cfg, older_than_days=30)
        assert "No measurements" in result

    def test_no_old_rows_returns_message(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _write_csv(
            cfg.measurements_csv,
            [{"timestamp_utc": _ts(5)}],
        )
        result = archive(cfg, older_than_days=30)
        assert "No rows older than" in result

    def test_creates_archive_file(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _write_csv(
            cfg.measurements_csv,
            [
                {"timestamp_utc": _ts(90)},
                {"timestamp_utc": _ts(5)},
            ],
        )
        archive(cfg, older_than_days=30)
        gz_files = list(cfg.archive_dir.glob("*.csv.gz"))
        assert len(gz_files) == 1

    def test_archive_file_is_readable_gzip(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _write_csv(
            cfg.measurements_csv,
            [{"timestamp_utc": _ts(90)}],
        )
        archive(cfg, older_than_days=30)
        gz_files = list(cfg.archive_dir.glob("*.csv.gz"))
        assert gz_files
        with gzip.open(gz_files[0], "rt", encoding="utf-8") as fh:
            content = fh.read()
        assert "timestamp_utc" in content  # header present

    def test_old_rows_removed_from_active(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _write_csv(
            cfg.measurements_csv,
            [
                {"timestamp_utc": _ts(90), "download_mbps": "50"},
                {"timestamp_utc": _ts(5), "download_mbps": "80"},
            ],
        )
        archive(cfg, older_than_days=30)
        with cfg.measurements_csv.open() as fh:
            reader = csv.DictReader(fh)
            remaining = list(reader)
        assert len(remaining) == 1
        assert remaining[0]["download_mbps"] == "80"

    def test_returns_summary_string(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _write_csv(
            cfg.measurements_csv,
            [{"timestamp_utc": _ts(60)}],
        )
        result = archive(cfg, older_than_days=30)
        assert "Archived" in result
        assert "1 rows" in result
