"""Weekly report: 7-day comparison table with sparkline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from netwatch.storage import csv_reader

_SPEED_COLS = ["download_mbps", "upload_mbps"]


@dataclass
class _DayStat:
    date: str
    count: int
    dl_mean: float | None
    ul_mean: float | None
    below: int
    failed: int


def _sparkline(values: list[float | None]) -> str:
    """Return an 8-block Unicode sparkline for a list of values."""
    blocks = " ▁▂▃▄▅▆▇█"
    clean = [v for v in values if v is not None]
    if not clean:
        return "─" * len(values)
    lo, hi = min(clean), max(clean)
    result = []
    for v in values:
        if v is None:
            result.append("·")
        elif hi == lo:
            result.append("▄")
        else:
            idx = int((v - lo) / (hi - lo) * 8)
            result.append(blocks[min(idx, 8)])
    return "".join(result)


def _parse_iso_week(week_str: str) -> tuple[date, date]:
    """Parse ``YYYY-WNN`` into (monday, sunday)."""
    year, w = week_str.split("-W")
    monday = date.fromisocalendar(int(year), int(w), 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def generate(csv_path: Path, week_str: str | None = None) -> str:
    """Return a Markdown weekly report.

    *week_str* is ISO format e.g. ``2026-W04``.  Defaults to current week.
    """
    today = date.today()
    if week_str is None:
        iso = today.isocalendar()
        week_str = f"{iso.year}-W{iso.week:02d}"

    monday, sunday = _parse_iso_week(week_str)

    rows = csv_reader.load(csv_path)

    # Build per-day data
    daily_stats: list[_DayStat] = []
    for offset in range(7):
        d = monday + timedelta(days=offset)
        day_rows = csv_reader.filter_by_date(rows, d.strftime("%Y-%m-%d"))
        agg = csv_reader.aggregate(day_rows, _SPEED_COLS)
        daily_stats.append(
            _DayStat(
                date=d.strftime("%Y-%m-%d"),
                count=len(day_rows),
                dl_mean=agg["download_mbps"]["mean"],
                ul_mean=agg["upload_mbps"]["mean"],
                below=csv_reader.below_contract_count(day_rows),
                failed=csv_reader.failed_count(day_rows),
            )
        )

    week_rows = [
        r for stat in daily_stats
        for r in csv_reader.filter_by_date(rows, stat.date)
    ]
    week_agg = csv_reader.aggregate(week_rows, _SPEED_COLS)

    spark = _sparkline([s.dl_mean for s in daily_stats])

    lines: list[str] = [
        f"# Weekly Report — {week_str}  ({monday} → {sunday})",
        "",
        f"**Sparkline (↓ download):** `{spark}`",
        "",
        "## Daily Breakdown",
        "",
        "| Date | Measurements | ↓ Mean | ↑ Mean | Below Contract | Failed |",
        "|------|-------------|--------|--------|----------------|--------|",
    ]
    for stat in daily_stats:
        dl = f"{stat.dl_mean:.1f}" if stat.dl_mean is not None else "—"
        ul = f"{stat.ul_mean:.1f}" if stat.ul_mean is not None else "—"
        lines.append(
            f"| {stat.date} | {stat.count} | {dl} | {ul} | {stat.below} | {stat.failed} |"
        )

    dl_w = f"{week_agg['download_mbps']['mean']:.1f}" if week_agg["download_mbps"]["mean"] else "—"
    ul_w = f"{week_agg['upload_mbps']['mean']:.1f}" if week_agg["upload_mbps"]["mean"] else "—"
    lines += [
        "",
        f"**Week average:** ↓ {dl_w} Mbps  ↑ {ul_w} Mbps",
    ]

    return "\n".join(lines)


def make_figures(csv_path: Path, week_str: str | None = None) -> list[Figure]:
    """Return matplotlib figures for the weekly report."""
    import matplotlib.pyplot as plt

    today = date.today()
    if week_str is None:
        iso = today.isocalendar()
        week_str = f"{iso.year}-W{iso.week:02d}"

    monday, sunday = _parse_iso_week(week_str)
    rows = csv_reader.load(csv_path)

    daily_stats: list[_DayStat] = []
    for offset in range(7):
        d = monday + timedelta(days=offset)
        day_rows = csv_reader.filter_by_date(rows, d.strftime("%Y-%m-%d"))
        agg = csv_reader.aggregate(day_rows, _SPEED_COLS)
        daily_stats.append(
            _DayStat(
                date=d.strftime("%a\n%m/%d"),
                count=len(day_rows),
                dl_mean=agg["download_mbps"]["mean"],
                ul_mean=agg["upload_mbps"]["mean"],
                below=csv_reader.below_contract_count(day_rows),
                failed=csv_reader.failed_count(day_rows),
            )
        )

    labels = [s.date for s in daily_stats]
    dl_vals = [s.dl_mean or 0.0 for s in daily_stats]
    ul_vals = [s.ul_mean or 0.0 for s in daily_stats]
    below_vals = [s.below for s in daily_stats]
    x = range(len(labels))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))

    width = 0.4
    ax1.bar([i - width / 2 for i in x], dl_vals, width, color="#0066cc", label="Download")
    ax1.bar([i + width / 2 for i in x], ul_vals, width, color="#00aa44", label="Upload")
    ax1.set_title(f"Daily Avg Speed — {week_str}", fontsize=13)
    ax1.set_ylabel("Mbps")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels)
    ax1.legend()
    ax1.grid(True, axis="y", alpha=0.3)

    ax2.bar(list(x), below_vals, color="#cc2200", label="Below contract")
    ax2.set_title("Below-Contract Measurements per Day", fontsize=13)
    ax2.set_ylabel("Count")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels)
    ax2.grid(True, axis="y", alpha=0.3)

    fig.tight_layout(pad=2.0)
    return [fig]
