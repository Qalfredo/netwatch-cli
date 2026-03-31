"""IP / ISP enrichment via ipinfo.io (with ip-api.com fallback)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_PRIMARY_URL = "https://ipinfo.io/json"
_FALLBACK_URL = "https://ip-api.com/json"
_TIMEOUT_S = 10.0


@dataclass
class IpInfoResult:
    """Public IP and ISP identity fields."""

    public_ip: str | None
    isp_name: str | None
    isp_asn: str | None
    error_message: str | None


def _parse_ipinfo(data: dict[str, object]) -> IpInfoResult:
    """Parse an ipinfo.io JSON response."""
    public_ip = str(data["ip"]) if "ip" in data else None
    org = str(data.get("org", "") or "")
    # org is formatted as "AS8048 CANTV Servicios Venezuela"
    if org:
        parts = org.split(" ", 1)
        asn = parts[0] if parts[0].startswith("AS") else None
        isp_name = parts[1] if len(parts) == 2 else (org if not asn else None)
    else:
        asn = None
        isp_name = None
    return IpInfoResult(public_ip, isp_name, asn, None)


def _parse_ipapi(data: dict[str, object]) -> IpInfoResult:
    """Parse an ip-api.com JSON response."""
    public_ip = str(data["query"]) if "query" in data else None
    isp_name = str(data["isp"]) if "isp" in data else None
    as_raw = str(data.get("as", "") or "")
    asn = as_raw.split(" ", 1)[0] if as_raw else None
    return IpInfoResult(public_ip, isp_name, asn or None, None)


def enrich(timeout_s: float = _TIMEOUT_S) -> IpInfoResult:
    """Fetch public IP and ISP info.  Never raises.

    Tries ipinfo.io first; falls back to ip-api.com.  If both fail, returns
    null-filled result with *error_message* set.
    """
    primary_error: str | None = None

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(_PRIMARY_URL)
            resp.raise_for_status()
            return _parse_ipinfo(resp.json())
    except Exception as exc:  # noqa: BLE001
        primary_error = str(exc)

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(_FALLBACK_URL)
            resp.raise_for_status()
            return _parse_ipapi(resp.json())
    except Exception as exc:  # noqa: BLE001
        return IpInfoResult(
            None,
            None,
            None,
            f"ipinfo.io failed: {primary_error}; ip-api.com failed: {exc}",
        )
