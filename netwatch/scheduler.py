"""launchd plist install / uninstall / status for automated collection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from netwatch.config import Config

_PLIST_LABEL = "com.netwatch.collect"
_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_PLIST_LABEL}.plist"
_TEMPLATE_PATH = Path(__file__).parent.parent / "launchd" / "com.netwatch.collect.plist.template"


def _render_plist(cfg: Config) -> str:
    """Read the plist template and substitute runtime values."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    venv_bin = str(Path(sys.executable).parent)
    subs = {
        "{{PYTHON_PATH}}": sys.executable,
        "{{INTERVAL_SECONDS}}": str(cfg.interval_minutes * 60),
        "{{DATA_DIR}}": str(cfg.data_dir),
        "{{VENV_BIN}}": venv_bin,
    }
    for key, val in subs.items():
        template = template.replace(key, val)
    return template


def install(cfg: Config) -> str:
    """Write the plist and load it via launchctl.  Returns a status message."""
    plist_content = _render_plist(cfg)
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(plist_content, encoding="utf-8")

    try:
        subprocess.run(
            ["/bin/launchctl", "load", "-w", str(_PLIST_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return f"launchctl load failed: {exc.stderr.strip()}"
    except FileNotFoundError:
        return "launchctl not found — are you on macOS?"

    return (
        f"Installed: {_PLIST_PATH}\n"
        f"Interval:  every {cfg.interval_minutes} minutes\n"
        f"Python:    {sys.executable}\n"
        f"Data dir:  {cfg.data_dir}"
    )


def uninstall() -> str:
    """Unload and remove the plist.  Returns a status message."""
    if not _PLIST_PATH.exists():
        return f"Plist not found: {_PLIST_PATH}"

    try:
        subprocess.run(
            ["/bin/launchctl", "unload", str(_PLIST_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return f"launchctl unload failed: {exc.stderr.strip()}"
    except FileNotFoundError:
        return "launchctl not found — are you on macOS?"

    _PLIST_PATH.unlink(missing_ok=True)
    return f"Uninstalled: {_PLIST_PATH}"


def status() -> str:
    """Return a human-readable launchd job status string."""
    try:
        result = subprocess.run(
            ["/bin/launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if _PLIST_LABEL in line:
                parts = line.split()
                pid = parts[0] if parts else "?"
                last_exit = parts[1] if len(parts) > 1 else "?"
                loaded_str = "running" if pid != "-" else "loaded (not running)"
                return (
                    f"Job:        {_PLIST_LABEL}\n"
                    f"State:      {loaded_str}\n"
                    f"PID:        {pid}\n"
                    f"Last exit:  {last_exit}\n"
                    f"Plist:      {_PLIST_PATH}"
                )
        installed = _PLIST_PATH.exists()
        return (
            f"Job {_PLIST_LABEL!r} not found in launchctl list.\n"
            f"Plist exists: {installed}\n"
            f"Run [bold]netwatch schedule install[/bold] to set up."
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return f"Could not query launchctl: {exc}"
