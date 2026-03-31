"""Unit tests for netwatch.storage.csv_writer."""

from __future__ import annotations

import csv
from pathlib import Path

from netwatch.config import load_config
from netwatch.models import MeasurementRow
from netwatch.storage.csv_writer import compute_below_contract, write_row


def _make_row(
    download_mbps: float | None = 80.0,
    upload_mbps: float | None = 8.0,
    error_message: str | None = None,
) -> MeasurementRow:
    return MeasurementRow(
        timestamp_utc="2026-01-15T10:00:00.000Z",
        timestamp_local="2026-01-15T07:00:00-03:00",
        download_mbps=download_mbps,
        upload_mbps=upload_mbps,
        ping_ms=20.0,
        jitter_ms=2.0,
        packet_loss_pct=0.0,
        isp_dns_ms=30.0,
        cloudflare_dns_ms=10.0,
        google_dns_ms=12.0,
        public_ip="1.2.3.4",
        isp_name="TestISP",
        isp_asn="AS1234",
        gateway_ip="192.168.1.1",
        gateway_vendor="Acme Router",
        topology="MODEM_COMBO",
        test_server="srv.example.com",
        test_server_dist_km=15.0,
        speed_backend="speedtest",
        contracted_down_mbps=100.0,
        contracted_up_mbps=10.0,
        below_contract=False,
        collection_duration_s=45.2,
        error_message=error_message,
    )


class TestComputeBelowContract:
    def test_above_threshold_returns_false(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        row = _make_row(download_mbps=90.0, upload_mbps=9.0)
        assert compute_below_contract(row, cfg) is False

    def test_download_below_threshold_returns_true(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        # contracted_down = 100, threshold = 80% → below 80 = True
        row = _make_row(download_mbps=75.0, upload_mbps=9.0)
        assert compute_below_contract(row, cfg) is True

    def test_upload_below_threshold_returns_true(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        # contracted_up = 10, threshold = 80% → below 8 = True
        row = _make_row(download_mbps=90.0, upload_mbps=7.0)
        assert compute_below_contract(row, cfg) is True

    def test_null_download_returns_true(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        row = _make_row(download_mbps=None, upload_mbps=9.0)
        assert compute_below_contract(row, cfg) is True

    def test_null_upload_returns_true(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        row = _make_row(download_mbps=90.0, upload_mbps=None)
        assert compute_below_contract(row, cfg) is True

    def test_exactly_at_threshold_returns_false(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        # 80% of 100 = 80; 80% of 10 = 8
        row = _make_row(download_mbps=80.0, upload_mbps=8.0)
        assert compute_below_contract(row, cfg) is False


class TestWriteRow:
    def _cfg(self, tmp_path: Path):  # type: ignore[no-untyped-def]
        p = tmp_path / "config.toml"
        p.write_text(
            f'[netwatch]\ndata_dir = "{tmp_path / "data"}"\n', encoding="utf-8"
        )
        return load_config(p)

    def test_creates_csv_file(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row())
        assert cfg.measurements_csv.exists()

    def test_creates_header_on_first_write(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row())
        with cfg.measurements_csv.open() as fh:
            first_line = fh.readline()
        assert "timestamp_utc" in first_line

    def test_no_duplicate_header_on_second_write(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row())
        write_row(cfg, _make_row())
        with cfg.measurements_csv.open() as fh:
            lines = fh.readlines()
        header_count = sum(1 for ln in lines if "timestamp_utc" in ln)
        assert header_count == 1

    def test_writes_two_data_rows(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row())
        write_row(cfg, _make_row())
        with cfg.measurements_csv.open() as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 2

    def test_null_fields_written_as_empty_string(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row(error_message=None))
        with cfg.measurements_csv.open() as fh:
            reader = csv.DictReader(fh)
            row = next(reader)
        assert row["error_message"] == ""

    def test_error_message_written(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row(error_message="timeout"))
        with cfg.measurements_csv.open() as fh:
            reader = csv.DictReader(fh)
            row = next(reader)
        assert row["error_message"] == "timeout"

    def test_creates_data_directory(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        assert not cfg.data_dir.exists()
        write_row(cfg, _make_row())
        assert cfg.data_dir.exists()

    def test_creates_logs_subdirectory(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        write_row(cfg, _make_row())
        assert cfg.logs_dir.exists()
