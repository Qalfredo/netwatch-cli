"""DNS latency probe: query three resolvers, return median of three attempts each."""

from __future__ import annotations

import random
import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median

_CLOUDFLARE = "1.1.1.1"
_GOOGLE = "8.8.8.8"
_DNS_PORT = 53
_QUERY_HOSTNAME = "google.com"
_ATTEMPTS = 3
_QUERY_TIMEOUT_S = 5.0


@dataclass
class DnsResult:
    """Median DNS latency (ms) per resolver."""

    isp_dns_ms: float | None
    cloudflare_dns_ms: float | None
    google_dns_ms: float | None
    error_message: str | None


def _build_dns_query(hostname: str) -> bytes:
    """Return a minimal DNS A-record query packet for *hostname*."""
    query_id = random.randint(1, 65535)
    flags = 0x0100  # standard query, recursion desired
    header = struct.pack(">HHHHHH", query_id, flags, 1, 0, 0, 0)
    labels = b""
    for label in hostname.split("."):
        enc = label.encode("ascii")
        labels += struct.pack("B", len(enc)) + enc
    labels += b"\x00"  # root label
    qtype_class = struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + labels + qtype_class


def _single_query(
    resolver_ip: str,
    hostname: str = _QUERY_HOSTNAME,
    timeout_s: float = _QUERY_TIMEOUT_S,
) -> float | None:
    """Send one DNS query to *resolver_ip*:53 and return round-trip ms, or None."""
    query = _build_dns_query(hostname)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout_s)
            t0 = time.perf_counter()
            sock.sendto(query, (resolver_ip, _DNS_PORT))
            sock.recv(512)
            return (time.perf_counter() - t0) * 1000.0
    except (OSError, TimeoutError):
        return None


def _median_query(
    resolver_ip: str,
    attempts: int = _ATTEMPTS,
) -> float | None:
    """Return the median RTT over *attempts* queries, or None if all fail."""
    times: list[float] = []
    for _ in range(attempts):
        t = _single_query(resolver_ip)
        if t is not None:
            times.append(t)
    return median(times) if times else None


def _get_isp_dns() -> str | None:
    """Return the first nameserver from /etc/resolv.conf, or None."""
    try:
        text = Path("/etc/resolv.conf").read_text(encoding="utf-8")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "nameserver":
                return parts[1]
    except OSError:
        pass
    return None


def probe() -> DnsResult:
    """Query ISP, Cloudflare, and Google DNS resolvers.

    Returns a :class:`DnsResult` with per-resolver median latency in ms.
    Never raises.
    """
    errors: list[str] = []

    isp_ip = _get_isp_dns()
    isp_ms: float | None = None
    if isp_ip:
        isp_ms = _median_query(isp_ip)
        if isp_ms is None:
            errors.append(f"ISP DNS ({isp_ip}) unreachable")
    else:
        errors.append("ISP DNS: could not determine resolver from /etc/resolv.conf")

    cf_ms = _median_query(_CLOUDFLARE)
    if cf_ms is None:
        errors.append(f"Cloudflare DNS ({_CLOUDFLARE}) unreachable")

    goog_ms = _median_query(_GOOGLE)
    if goog_ms is None:
        errors.append(f"Google DNS ({_GOOGLE}) unreachable")

    error_msg = "; ".join(errors) if errors else None
    return DnsResult(isp_ms, cf_ms, goog_ms, error_msg)
