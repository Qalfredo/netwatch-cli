"""Unit tests for netwatch.collector.latency."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from netwatch.collector.latency import LatencyResult, parse_ping_output, probe

# ---------------------------------------------------------------------------
# Parser tests — no subprocess
# ---------------------------------------------------------------------------

_TYPICAL_OUTPUT = """\
PING 1.1.1.1 (1.1.1.1): 56 data bytes
64 bytes from 1.1.1.1: icmp_seq=0 ttl=57 time=8.497 ms
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=9.134 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=9.876 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 8.497/9.169/9.876/0.564 ms
"""

_PARTIAL_LOSS_OUTPUT = """\
PING 1.1.1.1 (1.1.1.1): 56 data bytes
64 bytes from 1.1.1.1: icmp_seq=0 ttl=57 time=8.497 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 1 packets received, 66.7% packet loss
round-trip min/avg/max/stddev = 8.497/8.497/8.497/0.000 ms
"""

_FULL_LOSS_OUTPUT = """\
PING 1.1.1.1 (1.1.1.1): 56 data bytes

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 0 packets received, 100.0% packet loss
"""


class TestParsePingOutput:
    def test_typical_returns_correct_ping_ms(self) -> None:
        r = parse_ping_output(_TYPICAL_OUTPUT)
        assert r.ping_ms == pytest.approx(9.169)

    def test_typical_returns_correct_jitter(self) -> None:
        r = parse_ping_output(_TYPICAL_OUTPUT)
        assert r.jitter_ms == pytest.approx(0.564)

    def test_typical_returns_zero_loss(self) -> None:
        r = parse_ping_output(_TYPICAL_OUTPUT)
        assert r.packet_loss_pct == pytest.approx(0.0)

    def test_typical_no_error(self) -> None:
        r = parse_ping_output(_TYPICAL_OUTPUT)
        assert r.error_message is None

    def test_partial_loss(self) -> None:
        r = parse_ping_output(_PARTIAL_LOSS_OUTPUT)
        assert r.packet_loss_pct == pytest.approx(66.7)

    def test_full_loss_returns_100_pct(self) -> None:
        r = parse_ping_output(_FULL_LOSS_OUTPUT)
        assert r.packet_loss_pct == pytest.approx(100.0)

    def test_full_loss_ping_ms_is_none(self) -> None:
        r = parse_ping_output(_FULL_LOSS_OUTPUT)
        assert r.ping_ms is None

    def test_full_loss_no_error_message(self) -> None:
        r = parse_ping_output(_FULL_LOSS_OUTPUT)
        assert r.error_message is None

    def test_empty_output_returns_error(self) -> None:
        r = parse_ping_output("")
        assert r.error_message is not None
        assert r.ping_ms is None

    def test_missing_rtt_with_non_full_loss_returns_error(self) -> None:
        output = "3 packets transmitted, 2 packets received, 33.3% packet loss\n"
        r = parse_ping_output(output)
        assert r.error_message is not None


# ---------------------------------------------------------------------------
# probe() tests — subprocess mocked
# ---------------------------------------------------------------------------


class TestProbe:
    def _make_completed(self, stdout: str, returncode: int = 0) -> MagicMock:
        cp = MagicMock()
        cp.returncode = returncode
        cp.stdout = stdout
        cp.stderr = ""
        return cp

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_success_calls_ping_binary(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed(_TYPICAL_OUTPUT)
        probe("1.1.1.1", 3, 30.0)
        args = mock_run.call_args[0][0]
        assert args[0] == "/sbin/ping"

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_passes_count(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed(_TYPICAL_OUTPUT)
        probe("1.1.1.1", 5, 30.0)
        args = mock_run.call_args[0][0]
        assert "-c" in args
        assert "5" in args

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_passes_target(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed(_TYPICAL_OUTPUT)
        probe("8.8.8.8", 3, 30.0)
        args = mock_run.call_args[0][0]
        assert "8.8.8.8" in args

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_shell_false(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed(_TYPICAL_OUTPUT)
        probe("1.1.1.1", 3, 30.0)
        kwargs = mock_run.call_args[1]
        assert not kwargs.get("shell", False)

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_timeout_returns_null(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=30)
        result = probe("1.1.1.1", 3, 30.0)
        assert result.ping_ms is None
        assert result.error_message is not None

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_file_not_found_returns_null(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        result = probe("1.1.1.1", 3, 30.0)
        assert result.ping_ms is None
        assert result.error_message is not None

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_nonzero_exit_empty_stdout_returns_null(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed("", returncode=2)
        result = probe("1.1.1.1", 3, 30.0)
        assert result.ping_ms is None
        assert result.error_message is not None

    @patch("netwatch.collector.latency.subprocess.run")
    def test_probe_returns_latency_result_type(self, mock_run: MagicMock) -> None:
        mock_run.return_value = self._make_completed(_TYPICAL_OUTPUT)
        result = probe("1.1.1.1", 3, 30.0)
        assert isinstance(result, LatencyResult)
