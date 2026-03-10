"""
test_app_launcher.py — Unit tests for assistant/app_launcher.py
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from assistant.app_launcher import AppLauncher, _load_apps_yaml, _expand_path


class TestLoadAppsYaml:
    def test_returns_dict(self):
        result = _load_apps_yaml()
        assert isinstance(result, dict)

    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        """When apps.yaml does not exist, _load_apps_yaml returns {}."""
        import assistant.app_launcher as mod
        monkeypatch.setattr(mod, "_APPS_YAML", str(tmp_path / "nonexistent.yaml"))
        assert mod._load_apps_yaml() == {}


class TestExpandPath:
    def test_no_variable(self):
        assert _expand_path("notepad.exe") == "notepad.exe"

    @pytest.mark.skipif(
        not hasattr(os, "startfile"),
        reason="Windows-specific %VAR% expansion only works on Windows",
    )
    def test_with_env_variable(self, monkeypatch):
        monkeypatch.setenv("USERNAME", "testuser")
        result = _expand_path(r"C:\Users\%USERNAME%\Desktop")
        assert "testuser" in result


class TestAppLauncher:
    @pytest.fixture
    def launcher(self, tmp_path, monkeypatch):
        """Create a launcher with a temporary apps.yaml."""
        import assistant.app_launcher as mod
        apps_yaml = tmp_path / "apps.yaml"
        apps_yaml.write_text("notepad: notepad.exe\n", encoding="utf-8")
        monkeypatch.setattr(mod, "_APPS_YAML", str(apps_yaml))
        return AppLauncher()

    def test_open_known_app_from_yaml(self, launcher):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            result = launcher.open_app("notepad")
        assert "opening" in result.lower() or "notepad" in result.lower()

    def test_open_builtin_alias(self, launcher):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            result = launcher.open_app("calculator")
        assert "opening" in result.lower() or "calculator" in result.lower()

    def test_unknown_app_returns_error_message(self, launcher):
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = launcher.open_app("nonexistentapp12345")
        assert "could not" in result.lower() or "sorry" in result.lower()

    def test_case_insensitive(self, launcher):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            result = launcher.open_app("NOTEPAD")
        assert "notepad" in result.lower() or "opening" in result.lower()
