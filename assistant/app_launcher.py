"""
app_launcher.py — Launch Windows applications by name.

Resolution order:
  1. Look up the app name in ``config/apps.yaml`` (custom path mappings).
  2. Try ``os.startfile()`` with the raw name (works for known executables on
     the system PATH, e.g. ``notepad.exe``).
  3. Search Start Menu shortcut folders for a ``.lnk`` file whose stem matches
     the requested name.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

import yaml  # type: ignore

logger = logging.getLogger(__name__)

_APPS_YAML = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "apps.yaml"
)

# Directories that Windows uses to store Start Menu shortcuts
_START_MENU_DIRS = [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
]

# A small hard-coded alias table so common spoken names ("chrome",
# "calculator") always work even if apps.yaml is absent.
_BUILTIN_ALIASES: Dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "mozilla firefox": "firefox.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "control panel": "control.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
}


def _load_apps_yaml() -> Dict[str, str]:
    """Load the apps.yaml config, returning an empty dict on failure."""
    try:
        with open(_APPS_YAML, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return {k.lower(): v for k, v in data.items()}
    except FileNotFoundError:
        logger.warning("apps.yaml not found at %s", _APPS_YAML)
        return {}
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to load apps.yaml: %s", exc)
        return {}


def _expand_path(path: str) -> str:
    """Expand environment variables (e.g. %USERNAME%) in *path*."""
    return os.path.expandvars(path)


def _launch(executable: str) -> bool:
    """
    Try to launch *executable*.

    Returns True on success, False otherwise.
    """
    try:
        expanded = _expand_path(executable)
        if os.path.isabs(expanded):
            if not os.path.isfile(expanded):
                logger.debug("Executable not found at %s", expanded)
                return False
            subprocess.Popen([expanded], shell=False)  # nosec B603
        else:
            # Relative / bare name — let Windows PATH resolve it
            subprocess.Popen(expanded, shell=True)  # nosec B602
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("Launch failed for %r: %s", executable, exc)
        return False


def _search_start_menu(app_name: str) -> Optional[str]:
    """Return the path to the first matching Start Menu .lnk file, or None."""
    app_lower = app_name.lower()
    for directory in _START_MENU_DIRS:
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                stem = Path(fname).stem.lower()
                if app_lower in stem or stem in app_lower:
                    return os.path.join(root, fname)
    return None


class AppLauncher:
    """Open Windows applications by human-readable name."""

    def __init__(self) -> None:
        self._apps = _load_apps_yaml()

    def open_app(self, app_name: str) -> str:
        """
        Attempt to open the application identified by *app_name*.

        Parameters
        ----------
        app_name:
            The (case-insensitive) name of the application to open.

        Returns
        -------
        str
            A human-readable success or failure message.
        """
        name_lower = app_name.strip().lower()
        logger.info("Attempting to open: %r", name_lower)

        # 1. Check apps.yaml
        if name_lower in self._apps:
            path = self._apps[name_lower]
            if _launch(path):
                return f"Opening {app_name}."
            logger.debug("apps.yaml path failed, falling through.")

        # 2. Check built-in aliases
        if name_lower in _BUILTIN_ALIASES:
            exe = _BUILTIN_ALIASES[name_lower]
            if _launch(exe):
                return f"Opening {app_name}."
            logger.debug("Built-in alias failed, falling through.")

        # 3. Try the name as-is (e.g. if user said "notepad.exe")
        if _launch(name_lower):
            return f"Opening {app_name}."

        # 4. Search Start Menu shortcuts
        lnk = _search_start_menu(name_lower)
        if lnk:
            try:
                os.startfile(lnk)  # type: ignore[attr-defined]  # Windows only
                return f"Opening {app_name} via Start Menu."
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Start Menu launch failed: %s", exc)

        return (
            f"Sorry, I could not find or open '{app_name}'. "
            "Make sure the application is installed and its path is listed "
            "in config/apps.yaml."
        )
