"""Unit tests for netwatch.mcp_server.tools (all 11 tools)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from netwatch.mcp_server import tools
from netwatch.models import CSV_FIELDNAMES


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full: dict[str, str] = {k: "" for k in CSV_FIELDNAMES}
            full.update(row)
            writer.writerow(full)


def _sample_rows() -> list[dict[str, str]]:
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
            "packet_loss_pct": "3.5",
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
            "timestamp_utc": "2026-01-15T20:00:00.000Z",
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


def _patch_csv(tmp_path: Path) -> Path:
    p = tmp_path / "measurements_v1.csv"
    _write_csv(p, _sample_rows())
    return p


def _mock_cfg(csv_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.measurements_csv = csv_path
    cfg.max_rows_per_tool = 500
    return cfg


class TestGetLatestMeasurement:
    @patch("netwatch.mcp_server.tools._csv_path")
    def test_returns_json_string(self, mock_path: MagicMock, tmp_path: Path) -> None:
        mock_path.return_value = _patch_csv(tmp_path)
        result = tools.get_latest_measurement()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @patch("netwatch.mcp_server.tools._csv_path")
    def test_returns_last_row(self, mock_path: MagicMock, tmp_path: Path) -> None:
        mock_path.return_value = _patch_csv(tmp_path)
        result = json.loads(tools.get_latest_measurement())
        assert result.get("error_message") == "Timeout after 60s"

    @patch("netwatch.mcp_server.tools._csv_path")
    def test_empty_csv_returns_error(self, mock_path: MagicMock, tmp_path: Path) -> None:
        mock_path.return_value = tmp_path / "nonexistent.csv"
        result = json.loads(tools.get_latest_measurement())
        assert "error" in result


class TestGetSpeedSummary:
    @patch("netwatch.mcp_server.tools._csv_path")
    def test_returns_json(self, mock_path: MagicMock, tmp_path: Path) -> None:
        mock_path.return_value = _patch_csv(tmp_path)
        result = tools.get_speed_summary("2026-01-01")
        parsed = json.loads(result)
        assert "aggregates" in parsed

    @patch("netwatch.mcp_server.tools._csv_path")
    def test_invalid_date_returns_error(self, mock_path: MagicMock, tmp_path: Path) -> None:
        mock_path.return_value = _patch_csv(tmp_path)
        result = json.loads(tools.get_speed_summary("not-a-date"))
        assert "error" in result


class TestGetBelowContractRate:
    @patch("netwatch.mcp_server.tools._rows_since")
    def test_calculates_rate(self, mock_rows: MagicMock, tmp_path: Path) -> None:
        mock_rows.return_value = _sample_rows()
        result = json.loads(tools.get_below_contract_rate(since_days=365))
        assert result["total"] == 3
        assert result["below_contract"] == 2
        assert result["rate_pct"] == pytest.approx(66.67, abs=0.1)


class TestGetPacketLossIncidents:
    @patch("netwatch.mcp_server.tools._cfg")
    @patch("netwatch.mcp_server.tools._rows_since")
    def test_filters_by_threshold(
        self, mock_rows: MagicMock, mock_cfg_fn: MagicMock, tmp_path: Path
    ) -> None:
        mock_rows.return_value = _sample_rows()
        mock_cfg_fn.return_value = _mock_cfg(_patch_csv(tmp_path))
        result = json.loads(tools.get_packet_loss_incidents(since_days=365, min_loss_pct=1.0))
        # 2nd row has 3.5% loss
        assert result["count"] == 1


class TestGetConnectionDrops:
    @patch("netwatch.mcp_server.tools._cfg")
    @patch("netwatch.mcp_server.tools._rows_since")
    def test_finds_error_rows(
        self, mock_rows: MagicMock, mock_cfg_fn: MagicMock, tmp_path: Path
    ) -> None:
        mock_rows.return_value = _sample_rows()
        mock_cfg_fn.return_value = _mock_cfg(_patch_csv(tmp_path))
        result = json.loads(tools.get_connection_drops(since_days=365))
        assert result["count"] == 1


class TestGetDnsComparison:
    @patch("netwatch.mcp_server.tools._rows_since")
    def test_returns_three_resolvers(self, mock_rows: MagicMock, tmp_path: Path) -> None:
        mock_rows.return_value = _sample_rows()
        result = json.loads(tools.get_dns_comparison(since_days=365))
        assert "isp_dns_ms" in result["dns"]
        assert "cloudflare_dns_ms" in result["dns"]
        assert "google_dns_ms" in result["dns"]


class TestGetWorstHours:
    @patch("netwatch.mcp_server.tools._rows_since")
    def test_returns_sorted_list(self, mock_rows: MagicMock, tmp_path: Path) -> None:
        mock_rows.return_value = _sample_rows()
        result = json.loads(tools.get_worst_hours(since_days=365))
        hours = result["hours_ranked_worst_first"]
        assert isinstance(hours, list)
        if len(hours) >= 2:
            assert hours[0]["avg_download_mbps"] <= hours[-1]["avg_download_mbps"]


class TestGetDailyReport:
    @patch("netwatch.mcp_server.tools._cfg")
    def test_returns_markdown(self, mock_cfg_fn: MagicMock, tmp_path: Path) -> None:
        mock_cfg_fn.return_value = _mock_cfg(_patch_csv(tmp_path))
        result = tools.get_daily_report("2026-01-15")
        assert "Daily Report" in result


class TestRunCollect:
    @patch("netwatch.mcp_server.tools.subprocess.run")
    def test_returns_json_on_success(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.returncode = 0
        cp.stdout = "OK"
        cp.stderr = ""
        mock_run.return_value = cp
        result = json.loads(tools.run_collect())
        assert result["success"] is True

    @patch("netwatch.mcp_server.tools.subprocess.run")
    def test_timeout_returns_failure(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="netwatch", timeout=120)
        result = json.loads(tools.run_collect())
        assert result["success"] is False

    @patch("netwatch.mcp_server.tools.subprocess.run")
    def test_shell_false(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.returncode = 0
        cp.stdout = ""
        cp.stderr = ""
        mock_run.return_value = cp
        tools.run_collect()
        kwargs = mock_run.call_args[1]
        assert not kwargs.get("shell", False)


class TestExportCsvTool:
    @patch("netwatch.mcp_server.tools._cfg")
    def test_returns_csv_string(self, mock_cfg_fn: MagicMock, tmp_path: Path) -> None:
        mock_cfg_fn.return_value = _mock_cfg(_patch_csv(tmp_path))
        result = tools.export_csv_tool(since_days=365)
        assert "timestamp_utc" in result
