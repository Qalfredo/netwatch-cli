# netwatch-cli

ISP Accountability & Connection Health Monitor for macOS.

Periodically measures your internet connection's speed, latency, DNS performance, and network topology — writing everything to a tamper-evident CSV log. Generates ISP evidence reports suitable for regulatory complaints.

## Requirements

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Homebrew: `fping` (optional, for enhanced latency probes)

## Installation

```bash
# Using uv (recommended)
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run a measurement cycle
netwatch collect

# View status and last 5 measurements
netwatch status

# Show configuration
netwatch config show

# Install automated schedule (every 30 min via launchd)
netwatch schedule install

# Generate ISP evidence report
netwatch report isp --since 30 --format md
```

## Commands

| Command | Description |
|---|---|
| `netwatch collect` | Run a full measurement cycle |
| `netwatch collect --speed-only` | Speed + latency only |
| `netwatch collect --dry-run` | Run probes, print results, no CSV write |
| `netwatch status` | Last 5 measurements + config |
| `netwatch report daily` | Daily summary |
| `netwatch report weekly` | Weekly aggregate |
| `netwatch report monthly` | Monthly aggregate |
| `netwatch report isp` | ISP evidence report |
| `netwatch report export` | Export filtered CSV |
| `netwatch config show` | Print resolved config |
| `netwatch config edit` | Edit config in $EDITOR |
| `netwatch schedule install` | Install launchd job |
| `netwatch schedule uninstall` | Remove launchd job |
| `netwatch schedule status` | Show launchd job state |
| `netwatch archive --older-than N` | Compress rows older than N days |
| `netwatch mcp-server` | Start MCP stdio server |
| `netwatch mcp-server --print-config` | Print Claude Desktop config |

## Configuration

Config file: `~/.config/netwatch/config.toml` (auto-created with defaults on first run).

```toml
[netwatch]
data_dir  = "~/netwatch-data"
log_level = "WARNING"

[plan]
contracted_down_mbps         = 100.0
contracted_up_mbps           = 10.0
below_contract_threshold_pct = 80.0

[collection]
speed_backend   = "speedtest"
ping_target     = "1.1.1.1"
ping_count      = 10
probe_timeout_s = 60

[scheduler]
interval_minutes = 30

[mcp]
max_rows_per_tool = 500
```

## MCP Server (Claude Desktop Integration)

netwatch includes an [MCP](https://modelcontextprotocol.io) stdio server that exposes your connection data directly to Claude Desktop, letting you query and analyze your network health in plain language.

### Setup

```bash
# Print the config snippet for Claude Desktop
netwatch mcp-server --print-config
```

Add the output to `~/Library/Application Support/Claude/claude_desktop_config.json` under `"mcpServers"`, then restart Claude Desktop.

### Available Tools

| Tool | Description |
|---|---|
| `get_latest_measurement` | Most recent measurement row as JSON |
| `get_speed_summary` | Aggregated stats (mean/min/max/p95) over a date range |
| `get_isp_evidence_report` | Full ISP complaint report as Markdown |
| `get_below_contract_rate` | % of measurements below contracted speed |
| `get_packet_loss_incidents` | All loss events above a threshold |
| `get_connection_drops` | All failed measurement attempts |
| `get_dns_comparison` | ISP vs Cloudflare vs Google DNS latency |
| `get_worst_hours` | Hours ranked by worst avg download (VET) |
| `get_daily_report` | Daily Markdown report for a given date |
| `run_collect` | Trigger an immediate measurement cycle |
| `export_csv` | Raw CSV export as a string |

All timestamps returned by the MCP tools include `timestamp_vet` (Venezuela Standard Time, UTC-4) alongside UTC.

### Example Queries

Once connected, you can ask Claude things like:

- *"How was my connection this week?"*
- *"What are my worst hours for download speed?"*
- *"Generate an ISP evidence report for the last 7 days"*
- *"Run a measurement right now"*

## Data

All measurements are stored in `~/netwatch-data/measurements_v1.csv` — append-only, never modified after writing.

## Development

```bash
# Run tests
pytest -v

# Lint
ruff check .

# Type check
mypy --strict netwatch/
```
