"""Unit tests for netwatch.storage.csv_reader."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from netwatch.storage.csv_reader import (
    aggregate,
    below_contract_count,
    failed_count,
    filter_by_date,
    hourly_averages,
    load,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    from netwatch.models import CSV_FIELDNAMES

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # fill missing fields with empty string
            full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
            full.update(row)
            writer.writerow(full)


_ROWS: list[dict[str, str]] = [
    {
        "timestamp_utc": "2026-01-10T08:00:00.000Z",
        "download_mbps": "85.0",
        "upload_mbps": "9.5",
        "ping_ms": "20.0",
        "below_contract": "false",
        "error_message": "",
    },
    {
        "timestamp_utc": "2026-01-10T14:00:00.000Z",
        "download_mbps": "72.0",
        "upload_mbps": "7.0",
        "ping_ms": "45.0",
        "below_contract": "true",
        "error_message": "",
    },
    {
        "timestamp_utc": "2026-01-11T10:00:00.000Z",
        "download_mbps": "",
        "upload_mbps": "",
        "ping_ms": "",
        "below_contract": "true",
        "error_message": "Timeout after 60s",
    },
]


class TestLoad:
    def test_returns_empty_list_when_missing(self, tmp_path: Path) -> None:
        result = load(tmp_path / "nonexistent.csv")
        assert result == []

    def test_loads_all_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "measurements_v1.csv"
        _write_csv(p, _ROWS)
        result = load(p)
        assert len(result) == 3

    def test_rows_are_dicts(self, tmp_path: Path) -> None:
        p = tmp_path / "measurements_v1.csv"
        _write_csv(p, _ROWS)
        result = load(p)
        assert isinstance(result[0], dict)


class TestFilterByDate:
    def test_filters_by_date_prefix(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS)
        rows = load(p)
        result = filter_by_date(rows, "2026-01-10")
        assert len(result) == 2

    def test_returns_empty_for_unknown_date(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS)
        rows = load(p)
        result = filter_by_date(rows, "2099-01-01")
        assert result == []


class TestAggregate:
    def test_computes_mean(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS[:2])  # 85 and 72
        rows = load(p)
        agg = aggregate(rows, ["download_mbps"])
        assert agg["download_mbps"]["mean"] == pytest.approx(78.5)

    def test_computes_min(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS[:2])
        rows = load(p)
        agg = aggregate(rows, ["download_mbps"])
        assert agg["download_mbps"]["min"] == pytest.approx(72.0)

    def test_computes_max(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS[:2])
        rows = load(p)
        agg = aggregate(rows, ["download_mbps"])
        assert agg["download_mbps"]["max"] == pytest.approx(85.0)

    def test_returns_none_for_empty_column(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, [_ROWS[2]])  # row with no download_mbps
        rows = load(p)
        agg = aggregate(rows, ["download_mbps"])
        assert agg["download_mbps"]["mean"] is None

    def test_count_correct(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS[:2])
        rows = load(p)
        agg = aggregate(rows, ["download_mbps"])
        assert agg["download_mbps"]["count"] == 2


class TestBelowContractCount:
    def test_counts_true_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS)
        rows = load(p)
        assert below_contract_count(rows) == 2

    def test_empty_returns_zero(self) -> None:
        assert below_contract_count([]) == 0


class TestFailedCount:
    def test_counts_error_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS)
        rows = load(p)
        assert failed_count(rows) == 1

    def test_empty_returns_zero(self) -> None:
        assert failed_count([]) == 0


class TestHourlyAverages:
    def test_returns_correct_hour_bucket(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS[:2])
        rows = load(p)
        avgs = hourly_averages(rows, "download_mbps")
        assert avgs[8] == pytest.approx(85.0)   # 08:00
        assert avgs[14] == pytest.approx(72.0)  # 14:00

    def test_missing_values_yield_none(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _ROWS)
        rows = load(p)
        avgs = hourly_averages(rows, "download_mbps")
        assert avgs[10] is None  # row with no download_mbps at 10:00
