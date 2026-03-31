"""Unit tests for netwatch.enricher.ip_info."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from netwatch.enricher.ip_info import IpInfoResult, _parse_ipapi, _parse_ipinfo, enrich


class TestParseIpinfo:
    def test_extracts_ip(self) -> None:
        r = _parse_ipinfo({"ip": "1.2.3.4", "org": "AS8048 CANTV"})
        assert r.public_ip == "1.2.3.4"

    def test_extracts_asn(self) -> None:
        r = _parse_ipinfo({"ip": "1.2.3.4", "org": "AS8048 CANTV Servicios"})
        assert r.isp_asn == "AS8048"

    def test_extracts_isp_name(self) -> None:
        r = _parse_ipinfo({"ip": "1.2.3.4", "org": "AS8048 CANTV Servicios"})
        assert r.isp_name == "CANTV Servicios"

    def test_missing_org_gives_none(self) -> None:
        r = _parse_ipinfo({"ip": "5.6.7.8"})
        assert r.isp_asn is None
        assert r.isp_name is None

    def test_no_error_message(self) -> None:
        r = _parse_ipinfo({"ip": "1.2.3.4", "org": "AS1234 ISP"})
        assert r.error_message is None


class TestParseIpapi:
    def test_extracts_ip(self) -> None:
        r = _parse_ipapi({"query": "9.10.11.12", "isp": "MyISP", "as": "AS9999 MyISP LLC"})
        assert r.public_ip == "9.10.11.12"

    def test_extracts_isp_name(self) -> None:
        r = _parse_ipapi({"query": "9.10.11.12", "isp": "MyISP", "as": "AS9999 MyISP"})
        assert r.isp_name == "MyISP"

    def test_extracts_asn(self) -> None:
        r = _parse_ipapi({"query": "9.10.11.12", "isp": "MyISP", "as": "AS9999 MyISP"})
        assert r.isp_asn == "AS9999"


class TestEnrich:
    def _make_response(self, json_data: dict[str, object]) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock()
        return resp

    @patch("netwatch.enricher.ip_info.httpx.Client")
    def test_uses_ipinfo_primary(self, mock_client_cls: MagicMock) -> None:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.get.return_value = self._make_response({"ip": "1.2.3.4", "org": "AS1 ISP"})
        mock_client_cls.return_value = ctx
        result = enrich()
        assert result.public_ip == "1.2.3.4"

    @patch("netwatch.enricher.ip_info.httpx.Client")
    def test_falls_back_to_ipapi(self, mock_client_cls: MagicMock) -> None:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        # First call (ipinfo) fails, second (ipapi) succeeds
        ctx.get.side_effect = [
            Exception("connection refused"),
            self._make_response({"query": "5.6.7.8", "isp": "FALLBACK", "as": "AS99 FALLBACK"}),
        ]
        mock_client_cls.return_value = ctx
        result = enrich()
        assert result.public_ip == "5.6.7.8"

    @patch("netwatch.enricher.ip_info.httpx.Client")
    def test_both_fail_returns_null(self, mock_client_cls: MagicMock) -> None:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.get.side_effect = Exception("network down")
        mock_client_cls.return_value = ctx
        result = enrich()
        assert result.public_ip is None
        assert result.error_message is not None

    @patch("netwatch.enricher.ip_info.httpx.Client")
    def test_returns_ip_info_result_type(self, mock_client_cls: MagicMock) -> None:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.get.return_value = self._make_response({"ip": "1.1.1.1", "org": "AS13335 Cloudflare"})
        mock_client_cls.return_value = ctx
        result = enrich()
        assert isinstance(result, IpInfoResult)
