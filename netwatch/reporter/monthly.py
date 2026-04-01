"""Monthly report: weekly breakdown and 30-day aggregates."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from netwatch.storage import csv_reader

_SPEED_COLS = ["download_mbps", "upload_mbps"]
_LATENCY_COLS = ["ping_ms", "jitter_ms", "packet_loss_pct"]


def _weeks_in_month(year: int, month: int) -> list[tuple[date, date]]:
    """Return list of (monday, sunday) pairs covering every day of the month."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    weeks: list[tuple[date, date]] = []
    d = first - timedelta(days=first.weekday())  # back to Monday
    while d <= last:
        week_end = d + timedelta(days=6)
        weeks.append((d, week_end))
        d += timedelta(days=7)
    return weeks


def generate(csv_path: Path, month_str: str | None = None) -> str:
    """Return a Markdown monthly report.

    *month_str* is ``YYYY-MM``.  Defaults to current month.
    """
    today = date.today()
    if month_str is None:
        month_str = today.strftime("%Y-%m")

    year, month = int(month_str[:4]), int(month_str[5:7])
    rows = csv_reader.load(csv_path)

    # Filter rows for this month
    month_rows = [
        r for r in rows if r.get("timestamp_utc", "").startswith(month_str)
    ]

    total = len(month_rows)
    below = csv_reader.below_contract_count(month_rows)
    failed = csv_reader.failed_count(month_rows)
    agg = csv_reader.aggregate(month_rows, _SPEED_COLS + _LATENCY_COLS)

    lines: list[str] = [
        f"# Monthly Report — {month_str}",
        "",
        f"**Total measurements:** {total}  |  "
        f"**Below contract:** {below} ({below / total * 100:.0f}%)  |  "
        f"**Failed:** {failed}"
        if total else "No measurements for this month.",
        "",
    ]

    if total == 0:
        return "\n".join(lines)

    def _fmt(v: object) -> str:
        if v is None:
            return "—"
        return f"{float(v):.1f}"  # type: ignore[arg-type]

    lines += [
        "## Month Aggregates",
        "",
        "| Metric | Mean | Min | Max | p95 |",
        "|--------|------|-----|-----|-----|",
    ]
    for col in _SPEED_COLS + _LATENCY_COLS:
        a = agg[col]
        lines.append(
            f"| {col} | {_fmt(a['mean'])} | {_fmt(a['min'])} | {_fmt(a['max'])} | {_fmt(a['p95'])} |"  # noqa: E501
        )

    # Weekly breakdown
    weeks = _weeks_in_month(year, month)
    lines += [
        "",
        "## Weekly Breakdown",
        "",
        "| Week | Measurements | ↓ Mean | Below Contract |",
        "|------|-------------|--------|----------------|",
    ]

    best_week: tuple[str, float] | None = None
    worst_week: tuple[str, float] | None = None

    for mon, sun in weeks:
        week_rows = [
            r for r in month_rows
            if mon.strftime("%Y-%m-%d") <= r.get("timestamp_utc", "")[:10] <= sun.strftime("%Y-%m-%d")  # noqa: E501
        ]
        wa = csv_reader.aggregate(week_rows, ["download_mbps"])
        dl_mean = wa["download_mbps"]["mean"]
        week_label = f"{mon} – {sun}"
        below_w = csv_reader.below_contract_count(week_rows)
        lines.append(
            f"| {week_label} | {len(week_rows)} | {_fmt(dl_mean)} | {below_w} |"
        )
        if dl_mean is not None:
            if best_week is None or dl_mean > best_week[1]:
                best_week = (week_label, dl_mean)
            if worst_week is None or dl_mean < worst_week[1]:
                worst_week = (week_label, dl_mean)

    if best_week:
        lines += ["", f"**Best week:** {best_week[0]} ({best_week[1]:.1f} Mbps avg)"]
    if worst_week:
        lines += [f"**Worst week:** {worst_week[0]} ({worst_week[1]:.1f} Mbps avg)"]

    return "\n".join(lines)


def make_figures(csv_path: Path, month_str: str | None = None) -> list[Figure]:
    """Return matplotlib figures for the monthly report."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import UTC, datetime

    today = date.today()
    if month_str is None:
        month_str = today.strftime("%Y-%m")

    year, month = int(month_str[:4]), int(month_str[5:7])
    rows = csv_reader.load(csv_path)
    month_rows = [r for r in rows if r.get("timestamp_utc", "").startswith(month_str)]

    if not month_rows:
        return []

    # Build daily time-series for the month
    last_day = calendar.monthrange(year, month)[1]
    daily_dates, daily_dl, daily_below = [], [], []
    for day in range(1, last_day + 1):
        day_str = f"{month_str}-{day:02d}"
        day_rows = csv_reader.filter_by_date(month_rows, day_str)
        agg = csv_reader.aggregate(day_rows, ["download_mbps"])
        daily_dates.append(date(year, month, day))
        daily_dl.append(agg["download_mbps"]["mean"])
        daily_below.append(csv_reader.below_contract_count(day_rows))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))

    # Download time-series
    t = [d for d, v in zip(daily_dates, daily_dl) if v is not None]
    v = [v for v in daily_dl if v is not None]
    if t:
        ax1.plot(t, v, color="#0066cc", linewidth=1.8, marker="o", markersize=3)
        ax1.fill_between(t, v, alpha=0.12, color="#0066cc")
    ax1.set_title(f"Daily Avg Download — {month_str}", fontsize=13)
    ax1.set_ylabel("Mbps")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax1.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=30)

    # Below-contract bar
    colors = ["#cc2200" if b > 0 else "#cce8cc" for b in daily_below]
    ax2.bar(daily_dates, daily_below, color=colors, width=0.8)
    ax2.set_title("Below-Contract Measurements per Day", fontsize=13)
    ax2.set_ylabel("Count")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax2.grid(True, axis="y", alpha=0.3)
    fig.autofmt_xdate(rotation=30)

    fig.tight_layout(pad=2.0)
    return [fig]
