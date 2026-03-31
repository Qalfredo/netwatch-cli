"""Latency probe: ping(8) → avg RTT, jitter (stddev), packet-loss."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

# BSD ping summary: "round-trip min/avg/max/stddev = 7.9/9.2/11.2/0.9 ms"
_RTT_RE = re.compile(
    r"round-trip\s+min/avg/max/stddev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s+ms"
)
# Loss line: "10 packets transmitted, 10 packets received, 0.0% packet loss"
_LOSS_RE = re.compile(r"([\d.]+)%\s+packet loss")

_PING_BIN = "/sbin/ping"


@dataclass
class LatencyResult:
    """Result of one latency probe run."""

    ping_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float | None
    error_message: str | None


def _null(msg: str) -> LatencyResult:
    return LatencyResult(None, None, None, msg)


def parse_ping_output(output: str) -> LatencyResult:
    """Parse BSD ping(8) stdout into a :class:`LatencyResult`.

    Exposed so unit tests can exercise the parser without a real subprocess.
    """
    loss_match = _LOSS_RE.search(output)
    if loss_match is None:
        return _null("ping: packet-loss line not found in output")

    packet_loss_pct = float(loss_match.group(1))

    rtt_match = _RTT_RE.search(output)
    if rtt_match is None:
        # 100 % loss: ping prints no RTT line
        if packet_loss_pct >= 100.0:
            return LatencyResult(None, None, 100.0, None)
        return _null("ping: RTT summary line not found in output")

    ping_ms = float(rtt_match.group(2))   # avg
    jitter_ms = float(rtt_match.group(4))  # stddev

    return LatencyResult(ping_ms, jitter_ms, packet_loss_pct, None)


def probe(target: str, count: int, timeout_s: float) -> LatencyResult:
    """Run ``ping -c count target`` and return a :class:`LatencyResult`.

    Never raises; a failed probe returns null fields with *error_message* set.
    """
    try:
        result = subprocess.run(
            [_PING_BIN, "-c", str(count), target],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _null(f"ping: timed out after {timeout_s}s")
    except FileNotFoundError:
        return _null(f"ping: binary not found at {_PING_BIN}")
    except OSError as exc:
        return _null(f"ping: OS error: {exc}")

    # Non-zero exit with no stdout means the host was completely unreachable.
    if result.returncode != 0 and not result.stdout:
        return _null(f"ping: exited {result.returncode}: {result.stderr.strip()}")

    return parse_ping_output(result.stdout)
