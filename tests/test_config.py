"""Unit tests for netwatch.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from netwatch.config import load_config


class TestLoadConfigDefaults:
    """load_config() with no pre-existing file should produce defaults."""

    def test_creates_config_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        assert not config_file.exists()
        load_config(config_file)
        assert config_file.exists()

    def test_default_log_level(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.log_level == "WARNING"

    def test_default_contracted_down(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.contracted_down_mbps == 100.0

    def test_default_contracted_up(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.contracted_up_mbps == 10.0

    def test_default_below_contract_threshold_pct(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.below_contract_threshold_pct == 80.0

    def test_default_speed_backend(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.speed_backend == "speedtest"

    def test_default_ping_target(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.ping_target == "1.1.1.1"

    def test_default_ping_count(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.ping_count == 10

    def test_default_probe_timeout(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.probe_timeout_s == 60.0

    def test_default_interval_minutes(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.interval_minutes == 30

    def test_default_max_rows_per_tool(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.max_rows_per_tool == 500

    def test_data_dir_is_path(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert isinstance(cfg.data_dir, Path)

    def test_data_dir_is_absolute(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.data_dir.is_absolute()


class TestLoadConfigCustomValues:
    """load_config() should honour values written in the TOML file."""

    def _write_toml(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_custom_log_level(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, '[netwatch]\nlog_level = "DEBUG"\n')
        cfg = load_config(p)
        assert cfg.log_level == "DEBUG"

    def test_custom_contracted_down(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, "[plan]\ncontracted_down_mbps = 500.0\n")
        cfg = load_config(p)
        assert cfg.contracted_down_mbps == 500.0

    def test_custom_contracted_up(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, "[plan]\ncontracted_up_mbps = 50.0\n")
        cfg = load_config(p)
        assert cfg.contracted_up_mbps == 50.0

    def test_custom_ping_target(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, '[collection]\nping_target = "8.8.8.8"\n')
        cfg = load_config(p)
        assert cfg.ping_target == "8.8.8.8"

    def test_custom_ping_count(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, "[collection]\nping_count = 20\n")
        cfg = load_config(p)
        assert cfg.ping_count == 20

    def test_custom_data_dir(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / "my-data"
        p = tmp_path / "config.toml"
        self._write_toml(p, f'[netwatch]\ndata_dir = "{custom_dir}"\n')
        cfg = load_config(p)
        assert cfg.data_dir == custom_dir

    def test_custom_interval_minutes(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, "[scheduler]\ninterval_minutes = 15\n")
        cfg = load_config(p)
        assert cfg.interval_minutes == 15

    def test_custom_max_rows_per_tool(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(p, "[mcp]\nmax_rows_per_tool = 100\n")
        cfg = load_config(p)
        assert cfg.max_rows_per_tool == 100

    def test_iperf3_backend(self, tmp_path: Path) -> None:
        p = tmp_path / "config.toml"
        self._write_toml(
            p,
            '[collection]\nspeed_backend = "iperf3"\niperf3_server = "iperf.example.com:5201"\n',
        )
        cfg = load_config(p)
        assert cfg.speed_backend == "iperf3"
        assert cfg.iperf3_server == "iperf.example.com:5201"


class TestConfigProperties:
    """Derived properties on Config."""

    def test_measurements_csv_path(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.measurements_csv == cfg.data_dir / "measurements_v1.csv"

    def test_logs_dir_path(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.logs_dir == cfg.data_dir / "logs"

    def test_archive_dir_path(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.archive_dir == cfg.data_dir / "archive"

    def test_below_contract_threshold_fraction(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.below_contract_threshold == pytest.approx(0.80)

    def test_frozen_dataclass_immutable(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "config.toml")
        with pytest.raises((AttributeError, TypeError)):
            cfg.ping_count = 99  # type: ignore[misc]

    def test_idempotent_load(self, tmp_path: Path) -> None:
        """Loading the same file twice produces identical configs."""
        p = tmp_path / "config.toml"
        cfg1 = load_config(p)
        cfg2 = load_config(p)
        assert cfg1 == cfg2
