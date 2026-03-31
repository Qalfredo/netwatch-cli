"""Unit tests for netwatch.scheduler."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from netwatch.config import load_config
from netwatch.scheduler import install, status, uninstall


def _cfg(tmp_path: Path):  # type: ignore[no-untyped-def]
    p = tmp_path / "config.toml"
    p.write_text(
        f'[netwatch]\ndata_dir = "{tmp_path / "data"}"\n'
        "[scheduler]\ninterval_minutes = 15\n",
        encoding="utf-8",
    )
    return load_config(p)


class TestInstall:
    @patch("netwatch.scheduler.subprocess.run")
    def test_writes_plist_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        cfg = _cfg(tmp_path)

        with patch("netwatch.scheduler._PLIST_PATH", tmp_path / "com.netwatch.collect.plist"):
            install(cfg)

        assert (tmp_path / "com.netwatch.collect.plist").exists()

    @patch("netwatch.scheduler.subprocess.run")
    def test_plist_contains_interval_seconds(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        cfg = _cfg(tmp_path)
        plist_path = tmp_path / "com.netwatch.collect.plist"

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            install(cfg)

        content = plist_path.read_text()
        assert "900" in content  # 15 minutes × 60

    @patch("netwatch.scheduler.subprocess.run")
    def test_plist_contains_python_path(self, mock_run: MagicMock, tmp_path: Path) -> None:
        import sys

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        cfg = _cfg(tmp_path)
        plist_path = tmp_path / "com.netwatch.collect.plist"

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            install(cfg)

        content = plist_path.read_text()
        assert sys.executable in content

    @patch("netwatch.scheduler.subprocess.run")
    def test_calls_launchctl_load(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        cfg = _cfg(tmp_path)
        plist_path = tmp_path / "com.netwatch.collect.plist"

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            install(cfg)

        args = mock_run.call_args[0][0]
        assert "launchctl" in args[0]
        assert "load" in args

    @patch("netwatch.scheduler.subprocess.run")
    def test_launchctl_failure_returns_error_msg(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "launchctl", stderr="error")
        cfg = _cfg(tmp_path)
        plist_path = tmp_path / "com.netwatch.collect.plist"

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            result = install(cfg)

        assert "failed" in result.lower()

    @patch("netwatch.scheduler.subprocess.run")
    def test_launchctl_not_found_returns_message(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = FileNotFoundError
        cfg = _cfg(tmp_path)
        plist_path = tmp_path / "com.netwatch.collect.plist"

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            result = install(cfg)

        assert "not found" in result.lower()


class TestUninstall:
    @patch("netwatch.scheduler.subprocess.run")
    def test_returns_not_found_when_plist_missing(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        with patch("netwatch.scheduler._PLIST_PATH", tmp_path / "missing.plist"):
            result = uninstall()
        assert "not found" in result.lower()
        mock_run.assert_not_called()

    @patch("netwatch.scheduler.subprocess.run")
    def test_deletes_plist_on_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        plist_path = tmp_path / "com.netwatch.collect.plist"
        plist_path.write_text("dummy")

        with patch("netwatch.scheduler._PLIST_PATH", plist_path):
            uninstall()

        assert not plist_path.exists()


class TestStatus:
    @patch("netwatch.scheduler.subprocess.run")
    def test_returns_string(self, mock_run: MagicMock) -> None:
        cp = MagicMock()
        cp.stdout = "PID\tStatus\tLabel\n123\t0\tcom.netwatch.collect\n"
        mock_run.return_value = cp
        result = status()
        assert isinstance(result, str)

    @patch("netwatch.scheduler.subprocess.run")
    def test_not_installed_message(self, mock_run: MagicMock, tmp_path: Path) -> None:
        cp = MagicMock()
        cp.stdout = "PID\tStatus\tLabel\n"
        mock_run.return_value = cp
        with patch("netwatch.scheduler._PLIST_PATH", tmp_path / "missing.plist"):
            result = status()
        assert "not found" in result.lower() or "install" in result.lower()
