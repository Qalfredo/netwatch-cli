"""Monthly report: weekly breakdown and 30-day aggregates."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path

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
