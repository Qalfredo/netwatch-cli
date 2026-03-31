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
