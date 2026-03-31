"""Speed probe: speedtest-cli (Python API) or iperf3 (subprocess JSON mode)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from types import ModuleType

# Module-level import so tests can patch netwatch.collector.speed.speedtest.
try:
    import speedtest as speedtest
except ImportError:  # pragma: no cover
    speedtest: ModuleType | None = None  # type: ignore[no-redef]


@dataclass
class SpeedResult:
    """Result of one speed probe run."""

    download_mbps: float | None
    upload_mbps: float | None
    test_server: str | None
    test_server_dist_km: float | None
    speed_backend: str
    error_message: str | None


def _null(backend: str, msg: str) -> SpeedResult:
    return SpeedResult(None, None, None, None, backend, msg)


# ---------------------------------------------------------------------------
# speedtest-cli backend
# ---------------------------------------------------------------------------


def _probe_speedtest(timeout_s: float) -> SpeedResult:
    """Measure speed via the speedtest-cli Python API."""
    if speedtest is None:
        return _null("speedtest", "speedtest-cli not installed")

    try:
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        st.download()
        st.upload(pre_allocate=False)

        results = st.results.dict()
        download_mbps = results.get("download", 0) / 1e6
        upload_mbps = results.get("upload", 0) / 1e6

        server: dict[str, object] = results.get("server", {})
        host = str(server.get("host", "") or server.get("name", ""))
        dist_raw = server.get("d")
        dist_km = float(str(dist_raw)) if dist_raw is not None else None

        return SpeedResult(download_mbps, upload_mbps, host or None, dist_km, "speedtest", None)

    except Exception as exc:  # noqa: BLE001
        return _null("speedtest", f"speedtest error: {exc}")


# ---------------------------------------------------------------------------
# iperf3 backend
# ---------------------------------------------------------------------------


def _run_iperf3(
    host: str,
    port: int,
    reverse: bool,
    duration: int,
    timeout_s: float,
) -> dict[str, object]:
    """Run iperf3 in JSON mode and return parsed output dict."""
    args = [
        "iperf3",
        "-c", host,
        "-p", str(port),
        "-J",
        "-t", str(duration),
    ]
    if reverse:
        args.append("-R")

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def _probe_iperf3(server: str, timeout_s: float) -> SpeedResult:
    """Measure speed via iperf3 subprocess."""
    if not server:
        return _null("iperf3", "iperf3_server not configured")

    parts = server.rsplit(":", 1)
    host = parts[0]
    try:
        port = int(parts[1]) if len(parts) == 2 else 5201
    except ValueError:
        return _null("iperf3", f"invalid iperf3_server port in {server!r}")

    duration = 10

    try:
        dl_data = _run_iperf3(host, port, reverse=True, duration=duration, timeout_s=timeout_s)
        dl_bps = dl_data["end"]["sum_received"]["bits_per_second"]  # type: ignore[index]
        download_mbps = float(dl_bps) / 1e6
    except subprocess.TimeoutExpired:
        return _null("iperf3", f"iperf3 download timed out after {timeout_s}s")
    except (KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        return _null("iperf3", f"iperf3 download error: {exc}")

    try:
        ul_data = _run_iperf3(host, port, reverse=False, duration=duration, timeout_s=timeout_s)
        ul_bps = ul_data["end"]["sum_sent"]["bits_per_second"]  # type: ignore[index]
        upload_mbps = float(ul_bps) / 1e6
    except subprocess.TimeoutExpired:
        return _null("iperf3", f"iperf3 upload timed out after {timeout_s}s")
    except (KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        return _null("iperf3", f"iperf3 upload error: {exc}")

    return SpeedResult(download_mbps, upload_mbps, host, None, "iperf3", None)


# ---------------------------------------------------------------------------
# Public probe entry point
# ---------------------------------------------------------------------------


def probe(
    backend: str,
    iperf3_server: str,
    timeout_s: float,
) -> SpeedResult:
    """Run the configured speed probe and return a :class:`SpeedResult`.

    Never raises; a failed probe returns null fields with *error_message* set.
    """
    if backend == "iperf3":
        return _probe_iperf3(iperf3_server, timeout_s)
    return _probe_speedtest(timeout_s)
