"""ISP evidence report: comprehensive complaint-ready Markdown document."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from netwatch.storage import csv_reader

_SPEED_COLS = ["download_mbps", "upload_mbps"]
_LATENCY_COLS = ["ping_ms", "jitter_ms", "packet_loss_pct"]
_DNS_COLS = ["isp_dns_ms", "cloudflare_dns_ms", "google_dns_ms"]


def _fmt(val: float | None, unit: str = "", decimals: int = 1) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}{unit}"


def _pct(num: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{num / total * 100:.1f}%"


def _consecutive_failures(rows: list[dict[str, str]]) -> int:
    """Return the length of the longest consecutive run of below_contract=true or failed rows."""
    best = 0
    current = 0
    for row in rows:
        bad = (
            row.get("below_contract", "").lower() == "true"
            or bool(row.get("error_message", "").strip())
        )
        if bad:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def generate(csv_path: Path, since_days: int = 30, fmt: str = "md") -> str:
    """Return an ISP evidence report for the last *since_days* days.

    *fmt* is ``md`` (Markdown) or ``txt`` (plain text).
    """
    rows = csv_reader.load(csv_path)
    report_rows = csv_reader.filter_by_days(rows, since_days)

    total = len(report_rows)
    below = csv_reader.below_contract_count(report_rows)
    failed = csv_reader.failed_count(report_rows)
    agg = csv_reader.aggregate(report_rows, _SPEED_COLS + _LATENCY_COLS + _DNS_COLS)

    # Contracted values from the first row (or defaults)
    contracted_down: float = 100.0
    contracted_up: float = 10.0
    if report_rows:
        try:
            contracted_down = float(report_rows[0].get("contracted_down_mbps", "100") or "100")
            contracted_up = float(report_rows[0].get("contracted_up_mbps", "10") or "10")
        except ValueError:
            pass

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# ISP Evidence Report",
        "",
        f"**Generated:** {now}  |  **Period:** last {since_days} days  |  **Total measurements:** {total}",  # noqa: E501
        "",
    ]

    if total == 0:
        lines.append("_No measurements found for this period._")
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Contract vs Reality
    # -----------------------------------------------------------------------
    dl_mean = agg["download_mbps"]["mean"]
    ul_mean = agg["upload_mbps"]["mean"]
    dl_p50_vals = sorted([
        float(r["download_mbps"]) for r in report_rows if r.get("download_mbps")
    ])
    ul_p50_vals = sorted([
        float(r["upload_mbps"]) for r in report_rows if r.get("upload_mbps")
    ])
    dl_p50 = dl_p50_vals[len(dl_p50_vals) // 2] if dl_p50_vals else None
    ul_p50 = ul_p50_vals[len(ul_p50_vals) // 2] if ul_p50_vals else None

    lines += [
        "## Contract vs Reality",
        "",
        "| | Contracted | Mean | Median (p50) | p95 |",
        "|-|------------|------|--------------|-----|",
        f"| Download (Mbps) | {contracted_down:.1f} | {_fmt(dl_mean)} | {_fmt(dl_p50)} | {_fmt(agg['download_mbps']['p95'])} |",  # noqa: E501
        f"| Upload (Mbps)   | {contracted_up:.1f} | {_fmt(ul_mean)} | {_fmt(ul_p50)} | {_fmt(agg['upload_mbps']['p95'])} |",  # noqa: E501
        "",
        f"**Below-contract rate:** {below}/{total} measurements ({_pct(below, total)})",
        f"**Service failures (no measurement):** {failed} events",
        "",
    ]

    # -----------------------------------------------------------------------
    # Consecutive failures
    # -----------------------------------------------------------------------
    max_consec = _consecutive_failures(report_rows)
    lines += [
        "## Consecutive Degradation",
        "",
        f"Longest uninterrupted run of below-contract or failed measurements: **{max_consec}**",
        "",
    ]

    # -----------------------------------------------------------------------
    # Worst hours of day
    # -----------------------------------------------------------------------
    hourly = csv_reader.hourly_averages(report_rows, "download_mbps")
    active = [(h, v) for h, v in hourly.items() if v is not None]
    if active:
        worst_hours = sorted(active, key=lambda x: x[1])[:5]
        lines += [
            "## Worst Hours of Day (by avg download)",
            "",
            "| Hour (UTC) | Avg Download |",
            "|------------|-------------|",
        ]
        for h, v in worst_hours:
            lines.append(f"| {h:02d}:00 | {v:.1f} Mbps |")
        lines.append("")

    # -----------------------------------------------------------------------
    # DNS comparison
    # -----------------------------------------------------------------------
    isp_dns = agg["isp_dns_ms"]["mean"]
    cf_dns = agg["cloudflare_dns_ms"]["mean"]
    goog_dns = agg["google_dns_ms"]["mean"]
    lines += [
        "## DNS Resolver Comparison",
        "",
        "| Resolver | Mean Latency | Ratio vs ISP |",
        "|----------|-------------|--------------|",
        f"| ISP DNS | {_fmt(isp_dns, ' ms')} | 1.0× |",
        (
            f"| Cloudflare (1.1.1.1) | {_fmt(cf_dns, ' ms')} | {isp_dns / cf_dns:.1f}× slower |"
            if (isp_dns and cf_dns) else "| Cloudflare (1.1.1.1) | — | — |"
        ),
        (
            f"| Google (8.8.8.8) | {_fmt(goog_dns, ' ms')} | {isp_dns / goog_dns:.1f}× slower |"
            if (isp_dns and goog_dns) else "| Google (8.8.8.8) | — | — |"
        ),
        "",
    ]

    # -----------------------------------------------------------------------
    # Packet loss incidents
    # -----------------------------------------------------------------------
    loss_incidents = [
        r for r in report_rows
        if r.get("packet_loss_pct") and float(r["packet_loss_pct"]) >= 1.0
    ]
    lines += [
        f"## Packet Loss Incidents (≥1%) — {len(loss_incidents)} events",
        "",
    ]
    if loss_incidents:
        lines += ["| Timestamp | Loss % | Ping (ms) |", "|-----------|--------|-----------|"]
        for r in loss_incidents[:50]:  # cap at 50 for readability
            lines.append(
                f"| {r.get('timestamp_utc', '?')} | {r.get('packet_loss_pct', '?')} "
                f"| {r.get('ping_ms', '?')} |"
            )
        if len(loss_incidents) > 50:
            lines.append(f"_… and {len(loss_incidents) - 50} more incidents_")
    else:
        lines.append("_No packet loss incidents above 1% in this period._")
    lines.append("")

    # -----------------------------------------------------------------------
    # Connection drops (failed measurements)
    # -----------------------------------------------------------------------
    drops = [r for r in report_rows if r.get("error_message", "").strip()]
    lines += [
        f"## Connection Drops — {len(drops)} events",
        "",
    ]
    if drops:
        lines += ["| Timestamp | Error |", "|-----------|-------|"]
        for r in drops[:50]:
            lines.append(
                f"| {r.get('timestamp_utc', '?')} | {r.get('error_message', '?')} |"
            )
        if len(drops) > 50:
            lines.append(f"_… and {len(drops) - 50} more drops_")
    else:
        lines.append("_No connection drops recorded in this period._")
    lines.append("")

    # -----------------------------------------------------------------------
    # Test server consistency
    # -----------------------------------------------------------------------
    servers = Counter(r.get("test_server", "") for r in report_rows if r.get("test_server", ""))
    lines += [
        "## Test Server Consistency",
        "",
        "| Server | Measurements |",
        "|--------|-------------|",
    ]
    for srv, cnt in servers.most_common(10):
        lines.append(f"| {srv} | {cnt} |")
    lines.append("")

    return "\n".join(lines)


def make_figures(csv_path: Path, since_days: int = 30) -> list[Figure]:
    """Return matplotlib figures for the ISP evidence report."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    rows = csv_reader.load(csv_path)
    report_rows = csv_reader.filter_by_days(rows, since_days)

    if not report_rows:
        return []

    # Parse time-series
    times, downloads, pings = [], [], []
    below_flags = []
    for r in report_rows:
        try:
            ts = datetime.fromisoformat(r["timestamp_utc"].rstrip("Z")).replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        times.append(ts)
        downloads.append(float(r["download_mbps"]) if r.get("download_mbps") else None)
        pings.append(float(r["ping_ms"]) if r.get("ping_ms") else None)
        below_flags.append(r.get("below_contract", "").lower() == "true")

    figs: list[Figure] = []

    # Download scatter: color by below_contract
    fig, ax = plt.subplots(figsize=(10, 3.5))
    for i, (t, v, bad) in enumerate(zip(times, downloads, below_flags)):
        if v is None:
            continue
        ax.scatter(t, v, color="#cc2200" if bad else "#0066cc",
                   s=6, alpha=0.7, linewidths=0)
    # Thin line connecting points
    t_v = [(t, v) for t, v in zip(times, downloads) if v is not None]
    if t_v:
        ts_line, vs_line = zip(*t_v)
        ax.plot(ts_line, vs_line, color="#0066cc", linewidth=0.6, alpha=0.4)
    ax.set_title(f"Download Speed — last {since_days} days  (red = below contract)", fontsize=12)
    ax.set_ylabel("Mbps")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    figs.append(fig)

    # Hourly average bar chart
    hourly = csv_reader.hourly_averages(report_rows, "download_mbps")
    hours = list(range(24))
    h_vals = [hourly.get(h) or 0.0 for h in hours]
    fig2, ax2 = plt.subplots(figsize=(10, 3))
    bar_colors = ["#cc2200" if v < max(h_vals) * 0.8 and v > 0 else "#0066cc" for v in h_vals]
    ax2.bar(hours, h_vals, color=bar_colors)
    ax2.set_title("Avg Download by Hour of Day (UTC)", fontsize=12)
    ax2.set_xlabel("Hour (UTC)")
    ax2.set_ylabel("Mbps")
    ax2.set_xticks(hours)
    ax2.grid(True, axis="y", alpha=0.3)
    fig2.tight_layout()
    figs.append(fig2)

    return figs
