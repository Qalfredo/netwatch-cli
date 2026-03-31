"""Unit tests for netwatch.collector.speed."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from netwatch.collector.speed import SpeedResult, _probe_iperf3, _probe_speedtest, probe


class TestProbeSpeedtest:
    def _make_st_mock(
        self,
        download_bps: float = 50_000_000.0,
        upload_bps: float = 10_000_000.0,
        host: str = "speedtest.example.com",
        dist_km: float = 12.4,
    ) -> MagicMock:
        st = MagicMock()
        st.results.dict.return_value = {
            "download": download_bps,
            "upload": upload_bps,
            "server": {"host": host, "d": dist_km},
        }
        return st

    @patch("netwatch.collector.speed.speedtest")
    def test_returns_speed_result_type(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock()
        result = _probe_speedtest(60.0)
        assert isinstance(result, SpeedResult)

    @patch("netwatch.collector.speed.speedtest")
    def test_download_converted_to_mbps(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock(download_bps=100_000_000.0)
        result = _probe_speedtest(60.0)
        assert result.download_mbps == pytest.approx(100.0)

    @patch("netwatch.collector.speed.speedtest")
    def test_upload_converted_to_mbps(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock(upload_bps=20_000_000.0)
        result = _probe_speedtest(60.0)
        assert result.upload_mbps == pytest.approx(20.0)

    @patch("netwatch.collector.speed.speedtest")
    def test_server_host_stored(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock(host="srv.example.net")
        result = _probe_speedtest(60.0)
        assert result.test_server == "srv.example.net"

    @patch("netwatch.collector.speed.speedtest")
    def test_server_distance_stored(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock(dist_km=55.0)
        result = _probe_speedtest(60.0)
        assert result.test_server_dist_km == pytest.approx(55.0)

    @patch("netwatch.collector.speed.speedtest")
    def test_backend_label_is_speedtest(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.return_value = self._make_st_mock()
        result = _probe_speedtest(60.0)
        assert result.speed_backend == "speedtest"

    @patch("netwatch.collector.speed.speedtest")
    def test_exception_returns_null_result(self, mock_st_mod: MagicMock) -> None:
        mock_st_mod.Speedtest.side_effect = Exception("network error")
        result = _probe_speedtest(60.0)
        assert result.download_mbps is None
        assert result.error_message is not None

    @patch("netwatch.collector.speed.speedtest", None)
    def test_import_error_returns_null_result(self) -> None:
        result = _probe_speedtest(60.0)
        assert result.download_mbps is None
        assert result.error_message is not None


class TestProbeIperf3:
    def _iperf3_json(self, bps: float, sent: bool = False) -> str:
        key = "sum_sent" if sent else "sum_received"
        inner = {"bits_per_second": bps}
        return json.dumps({"end": {key: inner, "sum_sent": inner, "sum_received": inner}})

    @patch("netwatch.collector.speed.subprocess.run")
    def test_download_and_upload_calculated(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = self._iperf3_json(80_000_000.0)
        mock_run.return_value = cp
        result = _probe_iperf3("iperf.example.com:5201", 60.0)
        assert result.download_mbps == pytest.approx(80.0)
        assert result.upload_mbps == pytest.approx(80.0)

    @patch("netwatch.collector.speed.subprocess.run")
    def test_backend_label_is_iperf3(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = self._iperf3_json(50_000_000.0)
        mock_run.return_value = cp
        result = _probe_iperf3("iperf.example.com:5201", 60.0)
        assert result.speed_backend == "iperf3"

    def test_empty_server_returns_null(self) -> None:
        result = _probe_iperf3("", 60.0)
        assert result.download_mbps is None
        assert result.error_message is not None

    @patch("netwatch.collector.speed.subprocess.run")
    def test_timeout_returns_null(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="iperf3", timeout=60)
        result = _probe_iperf3("iperf.example.com:5201", 60.0)
        assert result.download_mbps is None
        assert result.error_message is not None

    @patch("netwatch.collector.speed.subprocess.run")
    def test_shell_false(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = self._iperf3_json(40_000_000.0)
        mock_run.return_value = cp
        _probe_iperf3("iperf.example.com:5201", 60.0)
        kwargs = mock_run.call_args[1]
        assert not kwargs.get("shell", False)


class TestProbeDispatch:
    @patch("netwatch.collector.speed._probe_speedtest")
    def test_speedtest_backend_dispatched(self, mock_st: MagicMock) -> None:
        mock_st.return_value = SpeedResult(50.0, 10.0, "host", 5.0, "speedtest", None)
        result = probe("speedtest", "", 60.0)
        mock_st.assert_called_once()
        assert result.speed_backend == "speedtest"

    @patch("netwatch.collector.speed._probe_iperf3")
    def test_iperf3_backend_dispatched(self, mock_ip: MagicMock) -> None:
        mock_ip.return_value = SpeedResult(50.0, 10.0, None, None, "iperf3", None)
        result = probe("iperf3", "host:5201", 60.0)
        mock_ip.assert_called_once()
        assert result.speed_backend == "iperf3"
