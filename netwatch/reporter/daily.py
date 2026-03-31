"""Daily report: per-metric aggregates for a single UTC day."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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
