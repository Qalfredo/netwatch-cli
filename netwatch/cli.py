"""netwatch-cli: main CLI entry point (all commands)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from netwatch.config import Config, load_config
from netwatch.models import MeasurementRow

app = typer.Typer(
    name="netwatch",
    help="ISP Accountability & Connection Health Monitor",
    no_args_is_help=True,
)
report_app = typer.Typer(help="Generate reports from collected measurements.")
config_app = typer.Typer(help="Manage netwatch configuration.")
schedule_app = typer.Typer(help="Manage the launchd collection schedule.")

app.add_typer(report_app, name="report")
app.add_typer(config_app, name="config")
app.add_typer(schedule_app, name="schedule")

console = Console()


def _get_config() -> Config:
    """Load configuration; exits with an error message on failure."""
    try:
        return load_config()
    except Exception as exc:
        console.print(f"[red]Failed to load config:[/red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


@app.command()
def collect(
    speed_only: Annotated[
        bool,
        typer.Option("--speed-only", help="Speed and latency only; skip DNS and enrichment."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Run all probes but print results without writing to CSV."),
    ] = False,
) -> None:
    """Run a full measurement cycle (speed + latency + DNS + enrichment)."""
    from netwatch.collector import dns, latency, speed
    from netwatch.enricher import ip_info, topology
    from netwatch.models import MeasurementRow
    from netwatch.storage import csv_writer

    cfg = _get_config()

    # Lower scheduling priority so collection doesn't impact user activity.
    os.nice(10)

    t_start = time.monotonic()

    console.print("[cyan]Running speed probe…[/cyan]")
    speed_result = speed.probe(cfg.speed_backend, cfg.iperf3_server, cfg.probe_timeout_s)

    console.print("[cyan]Running latency probe…[/cyan]")
    latency_result = latency.probe(cfg.ping_target, cfg.ping_count, cfg.probe_timeout_s)

    if not speed_only:
        console.print("[cyan]Running DNS probe…[/cyan]")
        dns_result = dns.probe()

        console.print("[cyan]Running enrichment…[/cyan]")
        ip_result = ip_info.enrich()
        topo_result = topology.detect()
    else:
        from netwatch.collector.dns import DnsResult
        from netwatch.enricher.ip_info import IpInfoResult
        from netwatch.enricher.topology import TopologyResult

        dns_result = DnsResult(None, None, None, "skipped (--speed-only)")
        ip_result = IpInfoResult(None, None, None, "skipped (--speed-only)")
        topo_result = TopologyResult(None, None, None, "skipped (--speed-only)")

    duration_s = time.monotonic() - t_start

    _VET = timezone(timedelta(hours=-4))
    now_utc = datetime.now(UTC)
    now_local = datetime.now().astimezone()
    now_vet = now_utc.astimezone(_VET)

    # Collect non-null error messages (ignore "skipped" markers)
    error_parts: list[str] = []
    for msg in [
        speed_result.error_message,
        latency_result.error_message,
        dns_result.error_message,
        ip_result.error_message,
        topo_result.error_message,
    ]:
        if msg and not msg.startswith("skipped"):
            error_parts.append(msg)
    error_msg = "; ".join(error_parts) if error_parts else None

    row = MeasurementRow(
        timestamp_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        timestamp_local=now_local.isoformat(),
        timestamp_vet=now_vet.strftime("%Y-%m-%dT%H:%M:%S") + "-04:00",
        download_mbps=speed_result.download_mbps,
        upload_mbps=speed_result.upload_mbps,
        ping_ms=latency_result.ping_ms,
        jitter_ms=latency_result.jitter_ms,
        packet_loss_pct=latency_result.packet_loss_pct,
        isp_dns_ms=dns_result.isp_dns_ms,
        cloudflare_dns_ms=dns_result.cloudflare_dns_ms,
        google_dns_ms=dns_result.google_dns_ms,
        public_ip=ip_result.public_ip,
        isp_name=ip_result.isp_name,
        isp_asn=ip_result.isp_asn,
        gateway_ip=topo_result.gateway_ip,
        gateway_vendor=topo_result.gateway_vendor,
        topology=topo_result.topology,
        test_server=speed_result.test_server,
        test_server_dist_km=speed_result.test_server_dist_km,
        speed_backend=speed_result.speed_backend,
        contracted_down_mbps=cfg.contracted_down_mbps,
        contracted_up_mbps=cfg.contracted_up_mbps,
        below_contract=csv_writer.compute_below_contract(row=MeasurementRow(
            # temp object for the computation — reuse all fields already set
            timestamp_utc="", timestamp_local="",
            download_mbps=speed_result.download_mbps,
            upload_mbps=speed_result.upload_mbps,
            ping_ms=None, jitter_ms=None, packet_loss_pct=None,
            isp_dns_ms=None, cloudflare_dns_ms=None, google_dns_ms=None,
            public_ip=None, isp_name=None, isp_asn=None,
            gateway_ip=None, gateway_vendor=None, topology=None,
            test_server=None, test_server_dist_km=None,
            speed_backend=speed_result.speed_backend,
            contracted_down_mbps=cfg.contracted_down_mbps,
            contracted_up_mbps=cfg.contracted_up_mbps,
            below_contract=False,
            collection_duration_s=0.0,
            error_message=None,
        ), cfg=cfg),
        collection_duration_s=round(duration_s, 2),
        error_message=error_msg,
    )

    if dry_run:
        _print_row(row)
    else:
        csv_writer.write_row(cfg, row)
        _print_row(row)

    status_color = "red" if row.below_contract else "green"
    console.print(
        f"\n[{status_color}]{'BELOW CONTRACT' if row.below_contract else 'OK'}[/{status_color}]"
        f"  ↓ {row.download_mbps or '?':.1f} Mbps  "
        f"↑ {row.upload_mbps or '?':.1f} Mbps  "
        f"ping {row.ping_ms or '?':.1f} ms  "
        f"({duration_s:.1f}s)"
    )


def _print_row(row: MeasurementRow) -> None:

    tbl = Table(show_header=True, header_style="bold")
    tbl.add_column("Metric")
    tbl.add_column("Value")
    pairs = [
        ("timestamp_utc", row.timestamp_utc),
        ("download_mbps", f"{row.download_mbps}" if row.download_mbps is not None else "—"),
        ("upload_mbps", f"{row.upload_mbps}" if row.upload_mbps is not None else "—"),
        ("ping_ms", f"{row.ping_ms}" if row.ping_ms is not None else "—"),
        ("jitter_ms", f"{row.jitter_ms}" if row.jitter_ms is not None else "—"),
        ("packet_loss_pct", f"{row.packet_loss_pct}" if row.packet_loss_pct is not None else "—"),
        ("isp_dns_ms", f"{row.isp_dns_ms}" if row.isp_dns_ms is not None else "—"),
        ("cloudflare_dns_ms", f"{row.cloudflare_dns_ms}" if row.cloudflare_dns_ms is not None
         else "—"),
        ("google_dns_ms", f"{row.google_dns_ms}" if row.google_dns_ms is not None else "—"),
        ("public_ip", row.public_ip or "—"),
        ("isp_name", row.isp_name or "—"),
        ("isp_asn", row.isp_asn or "—"),
        ("gateway_ip", row.gateway_ip or "—"),
        ("gateway_vendor", row.gateway_vendor or "—"),
        ("topology", row.topology or "—"),
        ("test_server", row.test_server or "—"),
        ("test_server_dist_km", f"{row.test_server_dist_km}" if row.test_server_dist_km is not None
         else "—"),
        ("speed_backend", row.speed_backend),
        ("below_contract", str(row.below_contract)),
        ("error_message", row.error_message or "—"),
    ]
    for k, v in pairs:
        tbl.add_row(k, str(v))
    console.print(tbl)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status() -> None:
    """Show last 5 measurements and current configuration."""
    from netwatch.storage import csv_reader

    cfg = _get_config()
    rows = csv_reader.load(cfg.measurements_csv)
    recent = rows[-5:]

    console.print(f"\n[bold]Config:[/bold] {cfg.data_dir}/measurements_v1.csv  "
                  f"({len(rows)} total rows)\n")

    if not recent:
        console.print(
            "[yellow]No measurements yet. Run [bold]netwatch collect[/bold] to start.[/yellow]"
        )
        raise typer.Exit(code=0)

    tbl = Table(show_header=True, header_style="bold")
    for col in ["timestamp_utc", "download_mbps", "upload_mbps", "ping_ms",
                "packet_loss_pct", "below_contract", "error_message"]:
        tbl.add_column(col)
    for row in recent:
        tbl.add_row(*[row.get(c, "") for c in
                      ["timestamp_utc", "download_mbps", "upload_mbps", "ping_ms",
                       "packet_loss_pct", "below_contract", "error_message"]])
    console.print(tbl)


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


@app.command()
def archive(
    older_than: Annotated[
        int,
        typer.Option("--older-than", help="Compress and remove rows older than N days."),
    ] = 90,
) -> None:
    """Compress and remove measurement rows older than N days."""
    from netwatch import archiver

    cfg = _get_config()
    console.print(archiver.archive(cfg, older_than))


# ---------------------------------------------------------------------------
# mcp-server
# ---------------------------------------------------------------------------


@app.command(name="mcp-server")
def mcp_server(
    print_config: Annotated[
        bool,
        typer.Option("--print-config", help="Print JSON config snippet for Claude Desktop."),
    ] = False,
) -> None:
    """Start the MCP stdio server for agent integration."""
    if print_config:
        import json

        snippet = {
            "mcpServers": {
                "netwatch": {
                    "command": sys.executable,
                    "args": ["-m", "netwatch", "mcp-server"],
                }
            }
        }
        console.print_json(json.dumps(snippet, indent=2))
        raise typer.Exit(code=0)

    from netwatch.mcp_server.server import run_server

    run_server()


# ---------------------------------------------------------------------------
# report subcommands
# ---------------------------------------------------------------------------


@report_app.command(name="daily")
def report_daily(
    date: Annotated[
        str | None,
        typer.Option("--date", help="Date to report on (YYYY-MM-DD). Defaults to today."),
    ] = None,
    save: Annotated[
        str | None,
        typer.Option("--save", help="Save .md and .pdf to this directory."),
    ] = None,
) -> None:
    """Daily summary — today or a specific date."""
    from netwatch.reporter import daily

    cfg = _get_config()
    report = daily.generate(cfg.measurements_csv, date)
    console.print(report)
    if save:
        from pathlib import Path
        from netwatch.reporter import renderer
        stem = f"daily_{date or __import__('datetime').date.today()}"
        figs = daily.make_figures(cfg.measurements_csv, date)
        md_path, pdf_path = renderer.save_report(report, Path(save), stem, figs)
        console.print(f"\n[green]Saved:[/green] {md_path}\n[green]Saved:[/green] {pdf_path}")


@report_app.command(name="weekly")
def report_weekly(
    week: Annotated[
        str | None,
        typer.Option("--week", help="ISO week to report on (YYYY-WNN)."),
    ] = None,
    save: Annotated[
        str | None,
        typer.Option("--save", help="Save .md and .pdf to this directory."),
    ] = None,
) -> None:
    """Weekly aggregate across all metrics."""
    from netwatch.reporter import weekly

    cfg = _get_config()
    report = weekly.generate(cfg.measurements_csv, week)
    console.print(report)
    if save:
        from pathlib import Path
        from netwatch.reporter import renderer
        if week is None:
            import datetime as _dt
            iso = _dt.date.today().isocalendar()
            week = f"{iso.year}-W{iso.week:02d}"
        stem = f"weekly_{week.replace('/', '-')}"
        figs = weekly.make_figures(cfg.measurements_csv, week)
        md_path, pdf_path = renderer.save_report(report, Path(save), stem, figs)
        console.print(f"\n[green]Saved:[/green] {md_path}\n[green]Saved:[/green] {pdf_path}")


@report_app.command(name="monthly")
def report_monthly(
    month: Annotated[
        str | None,
        typer.Option("--month", help="Month to report on (YYYY-MM)."),
    ] = None,
    save: Annotated[
        str | None,
        typer.Option("--save", help="Save .md and .pdf to this directory."),
    ] = None,
) -> None:
    """Monthly aggregate report."""
    from netwatch.reporter import monthly

    cfg = _get_config()
    report = monthly.generate(cfg.measurements_csv, month)
    console.print(report)
    if save:
        from pathlib import Path
        from netwatch.reporter import renderer
        import datetime as _dt
        stem = f"monthly_{month or _dt.date.today().strftime('%Y-%m')}"
        figs = monthly.make_figures(cfg.measurements_csv, month)
        md_path, pdf_path = renderer.save_report(report, Path(save), stem, figs)
        console.print(f"\n[green]Saved:[/green] {md_path}\n[green]Saved:[/green] {pdf_path}")


@report_app.command(name="isp")
def report_isp(
    since: Annotated[
        int,
        typer.Option("--since", help="Number of days to look back."),
    ] = 30,
    fmt: Annotated[
        str,
        typer.Option("--format", help="Output format: md or txt."),
    ] = "md",
    save: Annotated[
        str | None,
        typer.Option("--save", help="Save .md and .pdf to this directory."),
    ] = None,
) -> None:
    """ISP evidence report: below-contract summary, worst periods, drop count."""
    from netwatch.reporter import isp_evidence

    cfg = _get_config()
    report = isp_evidence.generate(cfg.measurements_csv, since, fmt)
    console.print(report)
    if save:
        from pathlib import Path
        from netwatch.reporter import renderer
        stem = f"isp_evidence_{since}d"
        figs = isp_evidence.make_figures(cfg.measurements_csv, since)
        md_path, pdf_path = renderer.save_report(report, Path(save), stem, figs)
        console.print(f"\n[green]Saved:[/green] {md_path}\n[green]Saved:[/green] {pdf_path}")


@report_app.command(name="export")
def report_export(
    since: Annotated[
        int,
        typer.Option("--since", help="Number of days to look back."),
    ] = 30,
    until: Annotated[
        str | None,
        typer.Option("--until", help="End date (YYYY-MM-DD), inclusive."),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path. Defaults to stdout."),
    ] = None,
) -> None:
    """Export filtered CSV suitable for attachment in a complaint."""
    from netwatch.reporter import export

    cfg = _get_config()
    if output:
        from pathlib import Path as P

        count = export.write_export_file(cfg.measurements_csv, P(output), since, until)
        console.print(f"[green]Exported {count} rows to {output}[/green]")
    else:
        console.print(export.export_csv(cfg.measurements_csv, since, until), end="")


# ---------------------------------------------------------------------------
# config subcommands
# ---------------------------------------------------------------------------


@config_app.command(name="show")
def config_show() -> None:
    """Print resolved configuration with defaults."""
    cfg = _get_config()
    console.print("[bold]netwatch configuration[/bold]")
    console.print(f"  data_dir                    = {cfg.data_dir}")
    console.print(f"  log_level                   = {cfg.log_level}")
    console.print(f"  contracted_down_mbps        = {cfg.contracted_down_mbps}")
    console.print(f"  contracted_up_mbps          = {cfg.contracted_up_mbps}")
    console.print(f"  below_contract_threshold_pct= {cfg.below_contract_threshold_pct}")
    console.print(f"  speed_backend               = {cfg.speed_backend}")
    console.print(f"  iperf3_server               = {cfg.iperf3_server!r}")
    console.print(f"  ping_target                 = {cfg.ping_target}")
    console.print(f"  ping_count                  = {cfg.ping_count}")
    console.print(f"  probe_timeout_s             = {cfg.probe_timeout_s}")
    console.print(f"  interval_minutes            = {cfg.interval_minutes}")
    console.print(f"  max_rows_per_tool           = {cfg.max_rows_per_tool}")


@config_app.command(name="edit")
def config_edit() -> None:
    """Open config.toml in $EDITOR."""
    from netwatch.config import _DEFAULT_CONFIG_PATH, _ensure_config_file

    _ensure_config_file(_DEFAULT_CONFIG_PATH)
    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run(
            [editor, str(_DEFAULT_CONFIG_PATH)],
            check=True,
        )
    except FileNotFoundError as err:
        console.print(f"[red]Editor not found:[/red] {editor}")
        raise typer.Exit(code=1) from err
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Editor exited with error:[/red] {exc.returncode}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# schedule subcommands
# ---------------------------------------------------------------------------


@schedule_app.command(name="install")
def schedule_install() -> None:
    """Write and load launchd plist for automated collection."""
    from netwatch import scheduler

    cfg = _get_config()
    console.print(scheduler.install(cfg))


@schedule_app.command(name="uninstall")
def schedule_uninstall() -> None:
    """Unload and delete the launchd plist."""
    from netwatch import scheduler

    console.print(scheduler.uninstall())


@schedule_app.command(name="status")
def schedule_status() -> None:
    """Show launchd job state and next run time."""
    from netwatch import scheduler

    console.print(scheduler.status())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Package entry point."""
    logging.basicConfig(level=logging.WARNING)
    app()


if __name__ == "__main__":
    main()
