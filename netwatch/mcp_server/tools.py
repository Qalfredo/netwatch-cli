"""All 11 netwatch MCP tool implementations."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from netwatch.config import Config, load_config
from netwatch.reporter import daily, isp_evidence
from netwatch.storage import csv_reader


def _cfg() -> Config:
    return load_config()


def _csv_path() -> Path:
    return _cfg().measurements_csv


def _rows_since(since_days: int) -> list[dict[str, str]]:
    rows = csv_reader.load(_csv_path())
    return csv_reader.filter_by_days(rows, since_days)


# ---------------------------------------------------------------------------
# Tool 1: get_latest_measurement
# ---------------------------------------------------------------------------


def get_latest_measurement() -> str:
    """Return the most recent complete measurement row as JSON."""
    rows = csv_reader.load(_csv_path())
    if not rows:
        return json.dumps({"error": "No measurements found."})
    return json.dumps(rows[-1])


# ---------------------------------------------------------------------------
# Tool 2: get_speed_summary
# ---------------------------------------------------------------------------


def get_speed_summary(since: str, until: str | None = None) -> str:
    """Return aggregated stats (mean/min/max/p95) over a date range.

    *since* and *until* are ISO dates (YYYY-MM-DD).
    """
    rows = csv_reader.load(_csv_path())
    try:
        start_dt = datetime.fromisoformat(since).replace(tzinfo=UTC)
    except ValueError:
        return json.dumps({"error": f"Invalid date: {since!r}"})

    end_dt = None
    if until:
        try:
            end_dt = datetime.fromisoformat(until).replace(hour=23, minute=59, second=59,
                                                           tzinfo=UTC)
        except ValueError:
            return json.dumps({"error": f"Invalid date: {until!r}"})

    filtered = csv_reader.filter_by_range(rows, start_dt, end_dt)
    cols = ["download_mbps", "upload_mbps", "ping_ms", "jitter_ms", "packet_loss_pct"]
    agg = csv_reader.aggregate(filtered, cols)
    return json.dumps({"rows": len(filtered), "aggregates": agg})


# ---------------------------------------------------------------------------
# Tool 3: get_isp_evidence_report
# ---------------------------------------------------------------------------


def get_isp_evidence_report(since_days: int = 30) -> str:
    """Return the full ISP evidence report as Markdown for the last N days."""
    cfg = _cfg()
    return isp_evidence.generate(
        cfg.measurements_csv, since_days,
        contracted_down=cfg.contracted_down_mbps,
        contracted_up=cfg.contracted_up_mbps,
    )


# ---------------------------------------------------------------------------
# Tool 4: get_below_contract_rate
# ---------------------------------------------------------------------------


def get_below_contract_rate(since_days: int = 30) -> str:
    """Return the percentage of measurements below contracted speed."""
    rows = _rows_since(since_days)
    total = len(rows)
    below = csv_reader.below_contract_count(rows)
    pct = below / total * 100 if total else 0.0
    return json.dumps({"since_days": since_days, "total": total, "below_contract": below,
                       "rate_pct": round(pct, 2)})


# ---------------------------------------------------------------------------
# Tool 5: get_packet_loss_incidents
# ---------------------------------------------------------------------------


def get_packet_loss_incidents(since_days: int = 30, min_loss_pct: float = 1.0) -> str:
    """Return all rows where packet loss exceeded *min_loss_pct* percent."""
    cfg = _cfg()
    rows = _rows_since(since_days)
    incidents = [
        r for r in rows
        if r.get("packet_loss_pct") and float(r["packet_loss_pct"]) >= min_loss_pct
    ]
    capped = incidents[:cfg.max_rows_per_tool]
    return json.dumps({"since_days": since_days, "min_loss_pct": min_loss_pct,
                       "count": len(incidents), "incidents": capped})


# ---------------------------------------------------------------------------
# Tool 6: get_connection_drops
# ---------------------------------------------------------------------------


def get_connection_drops(since_days: int = 30) -> str:
    """Return all failed measurement attempts (error_message non-empty)."""
    cfg = _cfg()
    rows = _rows_since(since_days)
    drops = [r for r in rows if r.get("error_message", "").strip()]
    capped = drops[:cfg.max_rows_per_tool]
    return json.dumps({"since_days": since_days, "count": len(drops), "drops": capped})


# ---------------------------------------------------------------------------
# Tool 7: get_dns_comparison
# ---------------------------------------------------------------------------


def get_dns_comparison(since_days: int = 30) -> str:
    """Return ISP DNS vs. public resolver latency summary."""
    rows = _rows_since(since_days)
    cols = ["isp_dns_ms", "cloudflare_dns_ms", "google_dns_ms"]
    agg = csv_reader.aggregate(rows, cols)
    return json.dumps({"since_days": since_days, "dns": agg})


# ---------------------------------------------------------------------------
# Tool 8: get_worst_hours
# ---------------------------------------------------------------------------


def get_worst_hours(since_days: int = 30) -> str:
    """Return hour-of-day breakdown ranked by average download speed."""
    rows = _rows_since(since_days)
    hourly = csv_reader.hourly_averages(rows, "download_mbps")
    ranked = sorted(
        [(h, v) for h, v in hourly.items() if v is not None],
        key=lambda x: x[1],
    )
    result: list[dict[str, Any]] = [{"hour_utc": h, "avg_download_mbps": round(v, 2)}
                                     for h, v in ranked]
    return json.dumps({"since_days": since_days, "hours_ranked_worst_first": result})


# ---------------------------------------------------------------------------
# Tool 9: get_daily_report
# ---------------------------------------------------------------------------


def get_daily_report(date: str) -> str:
    """Return a daily aggregate report as Markdown for the given date (YYYY-MM-DD)."""
    cfg = _cfg()
    return daily.generate(cfg.measurements_csv, date)


# ---------------------------------------------------------------------------
# Tool 10: run_collect
# ---------------------------------------------------------------------------


def run_collect() -> str:
    """Trigger an immediate measurement cycle and return the result."""
    try:
        result = subprocess.run(
            [str(Path(sys.executable).parent / "netwatch"), "collect"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.dumps({
            "success": result.returncode == 0,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "collect timed out after 120s"})
    except OSError as exc:
        return json.dumps({"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# Tool 11: export_csv
# ---------------------------------------------------------------------------


def export_csv_tool(since_days: int = 30) -> str:
    """Return raw CSV content as a string for the last N days."""
    cfg = _cfg()
    from netwatch.reporter import export as exp

    return exp.export_csv(cfg.measurements_csv, since_days)
