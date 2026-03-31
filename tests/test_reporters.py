"""Unit tests for reporter modules (daily, weekly, monthly, isp_evidence, export)."""

from __future__ import annotations

import csv
from pathlib import Path

from netwatch.models import CSV_FIELDNAMES
from netwatch.reporter import daily, export, isp_evidence, monthly, weekly


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
            full.update(row)
            writer.writerow(full)


def _make_rows() -> list[dict[str, str]]:
    return [
        {
            "timestamp_utc": "2026-01-15T08:00:00.000Z",
            "download_mbps": "85.0",
            "upload_mbps": "9.5",
            "ping_ms": "22.0",
            "jitter_ms": "3.0",
            "packet_loss_pct": "0.0",
            "isp_dns_ms": "80.0",
            "cloudflare_dns_ms": "10.0",
            "google_dns_ms": "11.0",
            "contracted_down_mbps": "100.0",
            "contracted_up_mbps": "10.0",
            "below_contract": "false",
            "error_message": "",
            "test_server": "srv1.example.com",
            "speed_backend": "speedtest",
        },
        {
            "timestamp_utc": "2026-01-15T14:00:00.000Z",
            "download_mbps": "72.0",
            "upload_mbps": "6.5",
            "ping_ms": "55.0",
            "jitter_ms": "15.0",
            "packet_loss_pct": "2.0",
            "isp_dns_ms": "150.0",
            "cloudflare_dns_ms": "12.0",
            "google_dns_ms": "13.0",
            "contracted_down_mbps": "100.0",
            "contracted_up_mbps": "10.0",
            "below_contract": "true",
            "error_message": "",
            "test_server": "srv1.example.com",
            "speed_backend": "speedtest",
        },
        {
            "timestamp_utc": "2026-01-16T10:00:00.000Z",
            "download_mbps": "",
            "upload_mbps": "",
            "ping_ms": "",
            "jitter_ms": "",
            "packet_loss_pct": "",
            "isp_dns_ms": "",
            "cloudflare_dns_ms": "",
            "google_dns_ms": "",
            "contracted_down_mbps": "100.0",
            "contracted_up_mbps": "10.0",
            "below_contract": "true",
            "error_message": "Timeout after 60s",
            "test_server": "",
            "speed_backend": "speedtest",
        },
    ]


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------


class TestDailyReport:
    def test_returns_string(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = daily.generate(p, "2026-01-15")
        assert isinstance(result, str)

    def test_contains_date(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = daily.generate(p, "2026-01-15")
        assert "2026-01-15" in result

    def test_contains_measurement_count(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = daily.generate(p, "2026-01-15")
        assert "2" in result  # 2 rows on 2026-01-15

    def test_no_data_returns_graceful_message(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = daily.generate(p, "2099-01-01")
        assert "No measurements" in result

    def test_missing_file_returns_graceful_message(self, tmp_path: Path) -> None:
        result = daily.generate(tmp_path / "nonexistent.csv", "2026-01-15")
        assert "No measurements" in result


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


class TestWeeklyReport:
    def test_returns_string(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = weekly.generate(p, "2026-W03")
        assert isinstance(result, str)

    def test_contains_week_label(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = weekly.generate(p, "2026-W03")
        assert "2026-W03" in result

    def test_contains_sparkline(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = weekly.generate(p, "2026-W03")
        assert "Sparkline" in result

    def test_sparkline_helper_all_none(self) -> None:
        from netwatch.reporter.weekly import _sparkline

        result = _sparkline([None, None, None])
        assert len(result) == 3

    def test_sparkline_helper_values(self) -> None:
        from netwatch.reporter.weekly import _sparkline

        result = _sparkline([10.0, 50.0, 100.0])
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Monthly
# ---------------------------------------------------------------------------


class TestMonthlyReport:
    def test_returns_string(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = monthly.generate(p, "2026-01")
        assert isinstance(result, str)

    def test_contains_month(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = monthly.generate(p, "2026-01")
        assert "2026-01" in result

    def test_no_data_returns_graceful(self, tmp_path: Path) -> None:
        result = monthly.generate(tmp_path / "nonexistent.csv", "2026-01")
        assert "No measurements" in result


# ---------------------------------------------------------------------------
# ISP Evidence
# ---------------------------------------------------------------------------


class TestIspEvidenceReport:
    def test_returns_string(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = isp_evidence.generate(p, since_days=365)
        assert isinstance(result, str)

    def test_contains_contract_section(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = isp_evidence.generate(p, since_days=365)
        assert "Contract vs Reality" in result

    def test_contains_dns_section(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = isp_evidence.generate(p, since_days=365)
        assert "DNS" in result

    def test_contains_drops_section(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = isp_evidence.generate(p, since_days=365)
        assert "Connection Drops" in result

    def test_consecutive_failures_count(self) -> None:
        from netwatch.reporter.isp_evidence import _consecutive_failures

        rows = [
            {"below_contract": "true", "error_message": ""},
            {"below_contract": "true", "error_message": ""},
            {"below_contract": "false", "error_message": ""},
            {"below_contract": "true", "error_message": ""},
        ]
        assert _consecutive_failures(rows) == 2

    def test_empty_csv_returns_graceful(self, tmp_path: Path) -> None:
        result = isp_evidence.generate(tmp_path / "nonexistent.csv", since_days=30)
        assert "No measurements" in result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_returns_csv_string(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = export.export_csv(p, since_days=365)
        assert "timestamp_utc" in result  # header

    def test_contains_data_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = export.export_csv(p, since_days=365)
        lines = result.strip().splitlines()
        assert len(lines) == 4  # 1 header + 3 rows

    def test_until_filter(self, tmp_path: Path) -> None:
        p = tmp_path / "m.csv"
        _write_csv(p, _make_rows())
        result = export.export_csv(p, since_days=365, until="2026-01-15")
        lines = result.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows on 2026-01-15

    def test_write_export_file(self, tmp_path: Path) -> None:
        src = tmp_path / "m.csv"
        _write_csv(src, _make_rows())
        out = tmp_path / "export.csv"
        count = export.write_export_file(src, out, since_days=365)
        assert out.exists()
        assert count == 3

    def test_empty_source_returns_header_only(self, tmp_path: Path) -> None:
        result = export.export_csv(tmp_path / "nonexistent.csv", since_days=30)
        assert "timestamp_utc" in result
        lines = result.strip().splitlines()
        assert len(lines) == 1  # header only
