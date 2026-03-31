"""Unit tests for netwatch.collector.dns."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from netwatch.collector.dns import (
    DnsResult,
    _build_dns_query,
    _get_isp_dns,
    _median_query,
    _single_query,
    probe,
)


class TestBuildDnsQuery:
    def test_returns_bytes(self) -> None:
        q = _build_dns_query("google.com")
        assert isinstance(q, bytes)

    def test_minimum_length(self) -> None:
        q = _build_dns_query("a.b")
        # header(12) + labels(1+1+1+1+1+1) + qtype_class(4) = at least 20
        assert len(q) >= 17

    def test_ends_with_a_record_class_in(self) -> None:
        q = _build_dns_query("google.com")
        # last 4 bytes: QTYPE=1 (A), QCLASS=1 (IN)
        import struct

        qtype, qclass = struct.unpack(">HH", q[-4:])
        assert qtype == 1
        assert qclass == 1

    def test_query_id_nonzero(self) -> None:
        import struct

        q = _build_dns_query("google.com")
        qid = struct.unpack(">H", q[:2])[0]
        assert 1 <= qid <= 65535


class TestGetIspDns:
    def test_returns_first_nameserver(self, tmp_path: Path) -> None:
        resolv = tmp_path / "resolv.conf"
        resolv.write_text("nameserver 192.168.1.1\nnameserver 8.8.8.8\n")
        with patch("netwatch.collector.dns.Path") as mock_path_cls:
            mock_path_cls.return_value = resolv
            result = _get_isp_dns()
        assert result == "192.168.1.1"

    def test_returns_none_when_file_missing(self) -> None:
        with patch("netwatch.collector.dns.Path") as mock_path_cls:
            mock_path_cls.return_value.read_text.side_effect = OSError("no file")
            result = _get_isp_dns()
        assert result is None

    def test_ignores_comment_lines(self, tmp_path: Path) -> None:
        resolv = tmp_path / "resolv.conf"
        resolv.write_text("# This is a comment\nnameserver 10.0.0.1\n")
        with patch("netwatch.collector.dns.Path") as mock_path_cls:
            mock_path_cls.return_value = resolv
            result = _get_isp_dns()
        assert result == "10.0.0.1"


class TestSingleQuery:
    @patch("netwatch.collector.dns.socket.socket")
    def test_returns_float_on_success(self, mock_socket_cls: MagicMock) -> None:
        sock = MagicMock()
        mock_socket_cls.return_value.__enter__ = MagicMock(return_value=sock)
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
        sock.recv.return_value = b"\x00" * 64
        result = _single_query("1.1.1.1")
        assert isinstance(result, float)
        assert result >= 0.0

    @patch("netwatch.collector.dns.socket.socket")
    def test_returns_none_on_timeout(self, mock_socket_cls: MagicMock) -> None:
        sock = MagicMock()
        mock_socket_cls.return_value.__enter__ = MagicMock(return_value=sock)
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
        sock.sendto.side_effect = socket_timeout()
        result = _single_query("1.1.1.1")
        assert result is None

    @patch("netwatch.collector.dns.socket.socket")
    def test_returns_none_on_os_error(self, mock_socket_cls: MagicMock) -> None:
        sock = MagicMock()
        mock_socket_cls.return_value.__enter__ = MagicMock(return_value=sock)
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
        sock.sendto.side_effect = OSError("network unreachable")
        result = _single_query("1.1.1.1")
        assert result is None


def socket_timeout() -> socket.timeout:  # type: ignore[valid-type]

    return TimeoutError("timed out")


import socket  # noqa: E402


class TestMedianQuery:
    @patch("netwatch.collector.dns._single_query")
    def test_returns_median_of_three(self, mock_query: MagicMock) -> None:
        mock_query.side_effect = [10.0, 20.0, 30.0]
        result = _median_query("1.1.1.1")
        assert result == pytest.approx(20.0)

    @patch("netwatch.collector.dns._single_query")
    def test_returns_none_when_all_fail(self, mock_query: MagicMock) -> None:
        mock_query.return_value = None
        result = _median_query("1.1.1.1")
        assert result is None

    @patch("netwatch.collector.dns._single_query")
    def test_ignores_failed_attempts(self, mock_query: MagicMock) -> None:
        mock_query.side_effect = [None, 15.0, None]
        result = _median_query("1.1.1.1")
        assert result == pytest.approx(15.0)


class TestProbe:
    @patch("netwatch.collector.dns._median_query")
    @patch("netwatch.collector.dns._get_isp_dns")
    def test_returns_dns_result(
        self, mock_isp: MagicMock, mock_median: MagicMock
    ) -> None:
        mock_isp.return_value = "192.168.1.1"
        mock_median.return_value = 12.5
        result = probe()
        assert isinstance(result, DnsResult)

    @patch("netwatch.collector.dns._median_query")
    @patch("netwatch.collector.dns._get_isp_dns")
    def test_all_resolvers_queried(
        self, mock_isp: MagicMock, mock_median: MagicMock
    ) -> None:
        mock_isp.return_value = "10.0.0.1"
        mock_median.return_value = 8.0
        result = probe()
        assert result.isp_dns_ms == pytest.approx(8.0)
        assert result.cloudflare_dns_ms == pytest.approx(8.0)
        assert result.google_dns_ms == pytest.approx(8.0)

    @patch("netwatch.collector.dns._median_query")
    @patch("netwatch.collector.dns._get_isp_dns")
    def test_error_when_isp_dns_missing(
        self, mock_isp: MagicMock, mock_median: MagicMock
    ) -> None:
        mock_isp.return_value = None
        mock_median.return_value = 10.0
        result = probe()
        assert result.error_message is not None
        assert result.isp_dns_ms is None

    @patch("netwatch.collector.dns._median_query")
    @patch("netwatch.collector.dns._get_isp_dns")
    def test_no_error_when_all_succeed(
        self, mock_isp: MagicMock, mock_median: MagicMock
    ) -> None:
        mock_isp.return_value = "192.168.0.1"
        mock_median.return_value = 5.0
        result = probe()
        assert result.error_message is None
