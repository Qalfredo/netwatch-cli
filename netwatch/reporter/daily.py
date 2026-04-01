"""Daily report: per-metric aggregates for a single UTC day."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from netwatch.storage import csv_reader

_SPEED_COLS = ["download_mbps", "upload_mbps"]
_LATENCY_COLS = ["ping_ms", "jitter_ms", "packet_loss_pct"]
_DNS_COLS = ["isp_dns_ms", "cloudflare_dns_ms", "google_dns_ms"]
_ALL_METRIC_COLS = _SPEED_COLS + _LATENCY_COLS + _DNS_COLS


def _fmt(val: float | None, decimals: int = 1) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


def generate(csv_path: Path, date_str: str | None = None) -> str:
    """Return a Markdown daily report for *date_str* (defaults to today UTC)."""
    target_date = date_str or datetime.now(UTC).strftime("%Y-%m-%d")
    rows = csv_reader.load(csv_path)
    day_rows = csv_reader.filter_by_date(rows, target_date)

    total = len(day_rows)
    below = csv_reader.below_contract_count(day_rows)
    failed = csv_reader.failed_count(day_rows)
    agg = csv_reader.aggregate(day_rows, _ALL_METRIC_COLS)

    lines: list[str] = [
        f"# Daily Report — {target_date}",
        "",
        f"**Measurements:** {total}  |  "
        f"**Below contract:** {below} ({below / total * 100:.0f}%)  |  "
        f"**Failed:** {failed}" if total else "No measurements found for this date.",
        "",
    ]

    if total == 0:
        return "\n".join(lines)

    lines += [
        "## Speed",
        "",
        "| Metric | Mean | Min | Max | p95 |",
        "|--------|------|-----|-----|-----|",
    ]
    for col in _SPEED_COLS:
        a = agg[col]
        lines.append(
            f"| {col} | {_fmt(a['mean'])} | {_fmt(a['min'])} | {_fmt(a['max'])} | {_fmt(a['p95'])} |"  # noqa: E501
        )

    lines += [
        "",
        "## Latency",
        "",
        "| Metric | Mean | Min | Max | p95 |",
        "|--------|------|-----|-----|-----|",
    ]
    for col in _LATENCY_COLS:
        a = agg[col]
        lines.append(
            f"| {col} | {_fmt(a['mean'])} | {_fmt(a['min'])} | {_fmt(a['max'])} | {_fmt(a['p95'])} |"  # noqa: E501
        )

    lines += [
        "",
        "## DNS",
        "",
        "| Resolver | Mean | Min | Max | p95 |",
        "|----------|------|-----|-----|-----|",
    ]
    labels = {
        "isp_dns_ms": "ISP",
        "cloudflare_dns_ms": "Cloudflare (1.1.1.1)",
        "google_dns_ms": "Google (8.8.8.8)",
    }
    for col in _DNS_COLS:
        a = agg[col]
        lines.append(
            f"| {labels[col]} | {_fmt(a['mean'])} | {_fmt(a['min'])} | {_fmt(a['max'])} | {_fmt(a['p95'])} |"  # noqa: E501
        )

    # Hour-of-day breakdown
    hourly = csv_reader.hourly_averages(day_rows, "download_mbps")
    active_hours = [(h, v) for h, v in hourly.items() if v is not None]
    if active_hours:
        lines += [
            "",
            "## Hourly Download Average",
            "",
            "| Hour (UTC) | Avg Download |",
            "|------------|-------------|",
        ]
        for h, v in sorted(active_hours):
            lines.append(f"| {h:02d}:00 | {_fmt(v)} Mbps |")

    return "\n".join(lines)


def make_figures(csv_path: Path, date_str: str | None = None) -> list[Figure]:
    """Return matplotlib figures for the daily report."""
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    target_date = date_str or datetime.now(UTC).strftime("%Y-%m-%d")
    rows = csv_reader.load(csv_path)
    day_rows = csv_reader.filter_by_date(rows, target_date)

    if not day_rows:
        return []

    times, downloads, uploads, pings = [], [], [], []
    for r in day_rows:
        try:
            ts = datetime.fromisoformat(r["timestamp_utc"].rstrip("Z")).replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        times.append(ts)
        downloads.append(float(r["download_mbps"]) if r.get("download_mbps") else None)
        uploads.append(float(r["upload_mbps"]) if r.get("upload_mbps") else None)
        pings.append(float(r["ping_ms"]) if r.get("ping_ms") else None)

    figs: list[Figure] = []

    # Speed chart
    fig, ax = plt.subplots(figsize=(10, 3.5))
    t_dl = [t for t, v in zip(times, downloads) if v is not None]
    v_dl = [v for v in downloads if v is not None]
    t_ul = [t for t, v in zip(times, uploads) if v is not None]
    v_ul = [v for v in uploads if v is not None]
    if t_dl:
        ax.plot(t_dl, v_dl, color="#0066cc", linewidth=1.5, label="Download (Mbps)")
    if t_ul:
        ax.plot(t_ul, v_ul, color="#00aa44", linewidth=1.5, label="Upload (Mbps)")
    ax.set_title(f"Speed — {target_date}", fontsize=13)
    ax.set_ylabel("Mbps")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    fig.autofmt_xdate(rotation=30)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    figs.append(fig)

    # Latency chart
    t_ping = [t for t, v in zip(times, pings) if v is not None]
    v_ping = [v for v in pings if v is not None]
    if t_ping:
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.plot(t_ping, v_ping, color="#cc6600", linewidth=1.5, label="Ping (ms)")
        ax2.set_title(f"Latency — {target_date}", fontsize=13)
        ax2.set_ylabel("ms")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        fig2.autofmt_xdate(rotation=30)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        fig2.tight_layout()
        figs.append(fig2)

    return figs
