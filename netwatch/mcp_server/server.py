"""FastMCP server exposing all 11 netwatch tools via stdio transport."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from netwatch.mcp_server import tools

mcp = FastMCP("netwatch")


@mcp.tool()
def get_latest_measurement() -> str:
    """Return the most recent complete measurement row as JSON."""
    return tools.get_latest_measurement()


@mcp.tool()
def get_speed_summary(since: str, until: str = "") -> str:
    """Return aggregated stats (mean/min/max/p95) over a date range.

    Args:
        since: Start date ISO-8601 (YYYY-MM-DD).
        until: End date ISO-8601 (YYYY-MM-DD), optional.
    """
    return tools.get_speed_summary(since, until or None)


@mcp.tool()
def get_isp_evidence_report(since_days: int = 30) -> str:
    """Return the full ISP evidence report as Markdown.

    Args:
        since_days: Number of days to look back (default 30).
    """
    return tools.get_isp_evidence_report(since_days)


@mcp.tool()
def get_below_contract_rate(since_days: int = 30) -> str:
    """Return the percentage of measurements below contracted speed.

    Args:
        since_days: Number of days to look back.
    """
    return tools.get_below_contract_rate(since_days)


@mcp.tool()
def get_packet_loss_incidents(since_days: int = 30, min_loss_pct: float = 1.0) -> str:
    """Return all rows where packet loss exceeded the threshold.

    Args:
        since_days: Number of days to look back.
        min_loss_pct: Minimum packet loss percentage to include (default 1.0).
    """
    return tools.get_packet_loss_incidents(since_days, min_loss_pct)


@mcp.tool()
def get_connection_drops(since_days: int = 30) -> str:
    """Return all failed measurement attempts with timestamps.

    Args:
        since_days: Number of days to look back.
    """
    return tools.get_connection_drops(since_days)


@mcp.tool()
def get_dns_comparison(since_days: int = 30) -> str:
    """Return ISP DNS vs. public resolver latency summary.

    Args:
        since_days: Number of days to look back.
    """
    return tools.get_dns_comparison(since_days)


@mcp.tool()
def get_worst_hours(since_days: int = 30) -> str:
    """Return hour-of-day breakdown ranked by average download speed (worst first).

    Args:
        since_days: Number of days to look back.
    """
    return tools.get_worst_hours(since_days)


@mcp.tool()
def get_daily_report(date: str) -> str:
    """Return a daily aggregate report as Markdown.

    Args:
        date: Date to report on (YYYY-MM-DD).
    """
    return tools.get_daily_report(date)


@mcp.tool()
def run_collect() -> str:
    """Trigger an immediate measurement cycle and return the result."""
    return tools.run_collect()


@mcp.tool()
def export_csv(since_days: int = 30) -> str:
    """Return raw CSV content as a string for download.

    Args:
        since_days: Number of days to export.
    """
    return tools.export_csv_tool(since_days)


def run_server() -> None:
    """Start the MCP stdio server (blocking)."""
    mcp.run()
