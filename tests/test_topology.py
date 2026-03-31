"""Unit tests for netwatch.enricher.topology and oui_db."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from netwatch.enricher import oui_db
from netwatch.enricher.topology import (
    TopologyResult,
    _classify_topology,
    _get_gateway_ip,
    _get_gateway_mac,
    detect,
)

# ---------------------------------------------------------------------------
# OUI database tests
# ---------------------------------------------------------------------------


class TestOuiLookup:
    def test_known_huawei_oui(self) -> None:
        vendor = oui_db.lookup("00:18:82:aa:bb:cc")
        assert vendor == "Huawei Technologies"

    def test_known_mikrotik_oui(self) -> None:
        vendor = oui_db.lookup("00:0C:42:11:22:33")
        assert vendor == "MikroTik"

    def test_unknown_oui_returns_none(self) -> None:
        vendor = oui_db.lookup("FF:FF:FF:AA:BB:CC")
        assert vendor is None

    def test_handles_dash_separator(self) -> None:
        vendor = oui_db.lookup("00-18-82-aa-bb-cc")
        assert vendor == "Huawei Technologies"

    def test_handles_no_separator(self) -> None:
        vendor = oui_db.lookup("001882AABBCC")
        assert vendor == "Huawei Technologies"

    def test_case_insensitive(self) -> None:
        vendor = oui_db.lookup("00:0c:42:11:22:33")
        assert vendor == "MikroTik"

    def test_short_mac_returns_none(self) -> None:
        vendor = oui_db.lookup("001")
        assert vendor is None


# ---------------------------------------------------------------------------
# Gateway IP extraction tests
# ---------------------------------------------------------------------------

_NETSTAT_OUTPUT = """\
Routing tables

Internet:
Destination        Gateway            Flags        Netif Expire
default            192.168.1.1        UGScg        en0
127.0.0.1          127.0.0.1          UH           lo0
"""


class TestGetGatewayIp:
    @patch("netwatch.enricher.topology.subprocess.run")
    def test_extracts_default_route(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _NETSTAT_OUTPUT
        mock_run.return_value = cp
        result = _get_gateway_ip()
        assert result == "192.168.1.1"

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_returns_none_when_no_default(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = "Routing tables\nInternet:\n"
        mock_run.return_value = cp
        result = _get_gateway_ip()
        assert result is None

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_shell_false(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _NETSTAT_OUTPUT
        mock_run.return_value = cp
        _get_gateway_ip()
        kwargs = mock_run.call_args[1]
        assert not kwargs.get("shell", False)


# ---------------------------------------------------------------------------
# ARP / MAC tests
# ---------------------------------------------------------------------------

_ARP_OUTPUT = "? (192.168.1.1) at a4:77:33:ab:cd:ef on en0 ifscope [ethernet]"


class TestGetGatewayMac:
    @patch("netwatch.enricher.topology.subprocess.run")
    def test_extracts_mac(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _ARP_OUTPUT
        mock_run.return_value = cp
        result = _get_gateway_mac("192.168.1.1")
        assert result == "a4:77:33:ab:cd:ef"

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_returns_none_when_not_found(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = "? (192.168.1.1) at (incomplete)"
        mock_run.return_value = cp
        result = _get_gateway_mac("192.168.1.1")
        assert result is None


# ---------------------------------------------------------------------------
# Topology classification tests
# ---------------------------------------------------------------------------

_DIRECT_TRACEROUTE = """\
traceroute to 8.8.8.8 (8.8.8.8), 3 hops max
 1  8.8.8.8 (8.8.8.8)  5.123 ms
"""

_MODEM_COMBO_TRACEROUTE = """\
traceroute to 8.8.8.8 (8.8.8.8), 3 hops max
 1  192.168.1.1 (192.168.1.1)  1.234 ms
 2  72.14.208.1 (72.14.208.1)  8.765 ms
"""

_MODEM_ROUTER_TRACEROUTE = """\
traceroute to 8.8.8.8 (8.8.8.8), 3 hops max
 1  192.168.1.1 (192.168.1.1)  1.234 ms
 2  10.0.0.1 (10.0.0.1)  3.456 ms
 3  72.14.208.1 (72.14.208.1)  9.012 ms
"""


class TestClassifyTopology:
    @patch("netwatch.enricher.topology.subprocess.run")
    def test_direct_no_private_hops(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _DIRECT_TRACEROUTE
        mock_run.return_value = cp
        assert _classify_topology() == "DIRECT"

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_modem_combo_one_private_hop(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _MODEM_COMBO_TRACEROUTE
        mock_run.return_value = cp
        assert _classify_topology() == "MODEM_COMBO"

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_modem_router_two_private_hops(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = _MODEM_ROUTER_TRACEROUTE
        mock_run.return_value = cp
        assert _classify_topology() == "MODEM_ROUTER"

    @patch("netwatch.enricher.topology.subprocess.run")
    def test_timeout_returns_direct(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="traceroute", timeout=20)
        assert _classify_topology() == "DIRECT"


# ---------------------------------------------------------------------------
# detect() integration
# ---------------------------------------------------------------------------


class TestDetect:
    @patch("netwatch.enricher.topology._classify_topology")
    @patch("netwatch.enricher.topology._get_gateway_mac")
    @patch("netwatch.enricher.topology._get_gateway_ip")
    def test_returns_topology_result(
        self,
        mock_ip: MagicMock,
        mock_mac: MagicMock,
        mock_topo: MagicMock,
    ) -> None:
        mock_ip.return_value = "192.168.1.1"
        mock_mac.return_value = "00:18:82:aa:bb:cc"
        mock_topo.return_value = "MODEM_COMBO"
        result = detect()
        assert isinstance(result, TopologyResult)
        assert result.gateway_ip == "192.168.1.1"
        assert result.gateway_vendor == "Huawei Technologies"
        assert result.topology == "MODEM_COMBO"

    @patch("netwatch.enricher.topology._classify_topology")
    @patch("netwatch.enricher.topology._get_gateway_mac")
    @patch("netwatch.enricher.topology._get_gateway_ip")
    def test_no_gateway_sets_error(
        self,
        mock_ip: MagicMock,
        mock_mac: MagicMock,
        mock_topo: MagicMock,
    ) -> None:
        mock_ip.return_value = None
        mock_mac.return_value = None
        mock_topo.return_value = "DIRECT"
        result = detect()
        assert result.error_message is not None
