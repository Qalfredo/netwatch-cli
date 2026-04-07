"""Configuration dataclass and TOML loader for netwatch-cli."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "netwatch" / "config.toml"

_DEFAULT_TOML = """\
[netwatch]
data_dir          = "~/netwatch-data"
log_level         = "WARNING"          # DEBUG | INFO | WARNING | ERROR

[plan]
contracted_down_mbps         = 1000.0
contracted_up_mbps           = 1000.0
below_contract_threshold_pct = 60.0   # flag if below this % of contracted

[collection]
speed_backend    = "speedtest"        # speedtest | iperf3
iperf3_server    = ""                 # host:port, required if backend = iperf3
ping_target      = "1.1.1.1"
ping_count       = 10
probe_timeout_s  = 60                 # abort probe if it exceeds this

[scheduler]
interval_minutes = 5                 # launchd StartInterval

[mcp]
max_rows_per_tool = 500
"""


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration loaded from config.toml."""

    # [netwatch]
    data_dir: Path
    log_level: str

    # [plan]
    contracted_down_mbps: float
    contracted_up_mbps: float
    below_contract_threshold_pct: float

    # [collection]
    speed_backend: str
    iperf3_server: str
    ping_target: str
    ping_count: int
    probe_timeout_s: float

    # [scheduler]
    interval_minutes: int

    # [mcp]
    max_rows_per_tool: int

    @property
    def measurements_csv(self) -> Path:
        """Absolute path to the primary measurements CSV file."""
        return self.data_dir / "measurements_v1.csv"

    @property
    def logs_dir(self) -> Path:
        """Absolute path to the logs directory."""
        return self.data_dir / "logs"

    @property
    def archive_dir(self) -> Path:
        """Absolute path to the archive directory."""
        return self.data_dir / "archive"

    @property
    def below_contract_threshold(self) -> float:
        """Fraction (0–1) used to determine below-contract status."""
        return self.below_contract_threshold_pct / 100.0


def _ensure_config_file(path: Path) -> None:
    """Create the config file with defaults if it does not exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_DEFAULT_TOML, encoding="utf-8")
        logger.info("Created default config at %s", path)


def load_config(path: Path | None = None) -> Config:
    """Load configuration from *path* (default: ~/.config/netwatch/config.toml).

    Creates the file with defaults if it does not exist.
    Returns a frozen :class:`Config` dataclass.
    """
    config_path = path if path is not None else _DEFAULT_CONFIG_PATH
    _ensure_config_file(config_path)

    with config_path.open("rb") as fh:
        raw: dict[str, object] = tomllib.load(fh)

    nw = raw.get("netwatch", {})
    plan = raw.get("plan", {})
    collection = raw.get("collection", {})
    scheduler = raw.get("scheduler", {})
    mcp = raw.get("mcp", {})

    assert isinstance(nw, dict)
    assert isinstance(plan, dict)
    assert isinstance(collection, dict)
    assert isinstance(scheduler, dict)
    assert isinstance(mcp, dict)

    data_dir_raw = nw.get("data_dir", "~/netwatch-data")
    assert isinstance(data_dir_raw, str)
    data_dir = Path(data_dir_raw).expanduser().resolve()

    log_level = str(nw.get("log_level", "WARNING")).upper()

    contracted_down = float(plan.get("contracted_down_mbps", 1000.0))
    contracted_up = float(plan.get("contracted_up_mbps", 1000.0))
    below_pct = float(plan.get("below_contract_threshold_pct", 60.0))

    speed_backend = str(collection.get("speed_backend", "speedtest"))
    iperf3_server = str(collection.get("iperf3_server", ""))
    ping_target = str(collection.get("ping_target", "1.1.1.1"))
    ping_count = int(collection.get("ping_count", 10))
    probe_timeout_s = float(collection.get("probe_timeout_s", 60.0))

    interval_minutes = int(scheduler.get("interval_minutes", 30))

    max_rows_per_tool = int(mcp.get("max_rows_per_tool", 500))

    return Config(
        data_dir=data_dir,
        log_level=log_level,
        contracted_down_mbps=contracted_down,
        contracted_up_mbps=contracted_up,
        below_contract_threshold_pct=below_pct,
        speed_backend=speed_backend,
        iperf3_server=iperf3_server,
        ping_target=ping_target,
        ping_count=ping_count,
        probe_timeout_s=probe_timeout_s,
        interval_minutes=interval_minutes,
        max_rows_per_tool=max_rows_per_tool,
    )
