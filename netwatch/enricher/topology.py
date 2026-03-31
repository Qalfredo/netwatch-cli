"""Network topology detection: gateway IP, vendor (OUI), and NAT depth."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from netwatch.enricher import oui_db

_NETSTAT_BIN = "/usr/sbin/netstat"
_ARP_BIN = "/usr/sbin/arp"
_TRACEROUTE_BIN = "/usr/sbin/traceroute"

# RFC-1918 private address ranges
_RFC1918_RE = re.compile(
    r"\b("
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r")\b"
)

# MAC address in arp output: "at a4:77:33:ab:cd:ef"
_MAC_RE = re.compile(
    r"\bat\s+([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})\b",
    re.IGNORECASE,
)


@dataclass
class TopologyResult:
    """Gateway identity and local network topology classification."""

    gateway_ip: str | None
    gateway_vendor: str | None
    topology: str | None  # DIRECT | MODEM_COMBO | MODEM_ROUTER
    error_message: str | None


def _get_gateway_ip() -> str | None:
    """Extract the IPv4 default-route gateway from ``netstat -rn``."""
    try:
        result = subprocess.run(
            [_NETSTAT_BIN, "-rn", "-f", "inet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            cols = line.split()
            if cols and cols[0] == "default":
                candidate = cols[1]
                # Ignore 'link#N' entries (no gateway IP yet)
                if not candidate.startswith("link#"):
                    return candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _get_gateway_mac(gateway_ip: str) -> str | None:
    """Return the MAC address of *gateway_ip* via ``arp -n``."""
    try:
        result = subprocess.run(
            [_ARP_BIN, "-n", gateway_ip],
            capture_output=True,
            text=True,
            timeout=5,
        )
        m = _MAC_RE.search(result.stdout)
        if m:
            return m.group(1)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _classify_topology() -> str:
    """Run a short traceroute and count distinct RFC-1918 hops.

    Returns one of: ``DIRECT``, ``MODEM_COMBO``, ``MODEM_ROUTER``.
    """
    try:
        result = subprocess.run(
            [_TRACEROUTE_BIN, "-m", "3", "-w", "1", "8.8.8.8"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        private_hops = set(_RFC1918_RE.findall(result.stdout))
        if len(private_hops) >= 2:
            return "MODEM_ROUTER"
        if len(private_hops) == 1:
            return "MODEM_COMBO"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "DIRECT"


def detect() -> TopologyResult:
    """Detect gateway IP, vendor, and NAT topology.  Never raises."""
    errors: list[str] = []

    gateway_ip = _get_gateway_ip()
    if gateway_ip is None:
        errors.append("could not determine gateway IP")

    gateway_vendor: str | None = None
    if gateway_ip:
        mac = _get_gateway_mac(gateway_ip)
        if mac:
            gateway_vendor = oui_db.lookup(mac)
        else:
            errors.append(f"ARP lookup failed for {gateway_ip}")

    try:
        topology = _classify_topology()
    except Exception as exc:  # noqa: BLE001
        topology = None
        errors.append(f"traceroute failed: {exc}")

    error_msg = "; ".join(errors) if errors else None
    return TopologyResult(gateway_ip, gateway_vendor, topology, error_msg)
