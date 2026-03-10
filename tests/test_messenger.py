"""
test_messenger.py — Unit tests for assistant/messenger.py

All network calls (SMTP, pywhatkit) are mocked so no real messages are sent.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock

from assistant.messenger import Messenger


# ---------------------------------------------------------------------------
# Helper — fake pywhatkit module (not installed in test environment)
# ---------------------------------------------------------------------------

def _make_fake_pywhatkit(side_effect=None):
    """Return a MagicMock that stands in for the pywhatkit module."""
    fake = MagicMock()
    if side_effect is not None:
        fake.sendwhatmsg.side_effect = side_effect
    return fake


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def configured_messenger(tmp_path, monkeypatch):
    """Return a Messenger backed by a temp settings.yaml with real-looking creds."""
    settings_content = """
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "test@gmail.com"
  sender_password: "test_app_password"

whatsapp_contacts:
  John: "+1234567890"
  Mom: "+0987654321"
"""
    settings_yaml = tmp_path / "settings.yaml"
    settings_yaml.write_text(settings_content, encoding="utf-8")

    import assistant.messenger as mod
    monkeypatch.setattr(mod, "_SETTINGS_YAML", str(settings_yaml))
    return Messenger()


@pytest.fixture
def unconfigured_messenger(tmp_path, monkeypatch):
    """Return a Messenger whose settings.yaml has placeholder credentials."""
    settings_content = """
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your_email@gmail.com"
  sender_password: "your_app_password"

whatsapp_contacts: {}
"""
    settings_yaml = tmp_path / "settings.yaml"
    settings_yaml.write_text(settings_content, encoding="utf-8")

    import assistant.messenger as mod
    monkeypatch.setattr(mod, "_SETTINGS_YAML", str(settings_yaml))
    return Messenger()


# ---------------------------------------------------------------------------
# WhatsApp tests
# ---------------------------------------------------------------------------

class TestSendWhatsApp:
    def test_known_contact_success(self, configured_messenger):
        fake_kit = _make_fake_pywhatkit()
        with patch.dict(sys.modules, {"pywhatkit": fake_kit}):
            result = configured_messenger.send_whatsapp("John", "hello there")
        assert "sent" in result.lower()
        fake_kit.sendwhatmsg.assert_called_once()

    def test_known_contact_case_insensitive(self, configured_messenger):
        fake_kit = _make_fake_pywhatkit()
        with patch.dict(sys.modules, {"pywhatkit": fake_kit}):
            result = configured_messenger.send_whatsapp("john", "hi")
        assert "sent" in result.lower()
        fake_kit.sendwhatmsg.assert_called_once()

    def test_unknown_contact_returns_error(self, configured_messenger):
        result = configured_messenger.send_whatsapp("UnknownPerson", "hello")
        assert "not found" in result.lower()

    def test_empty_contacts_returns_error(self, unconfigured_messenger):
        result = unconfigured_messenger.send_whatsapp("John", "hi")
        assert "not found" in result.lower()

    def test_pywhatkit_import_error(self, configured_messenger):
        # Remove pywhatkit from sys.modules to simulate ImportError
        with patch.dict(sys.modules, {"pywhatkit": None}):
            result = configured_messenger.send_whatsapp("John", "hello")
        assert "not installed" in result.lower() or "failed" in result.lower()

    def test_pywhatkit_exception_returns_error(self, configured_messenger):
        fake_kit = _make_fake_pywhatkit(side_effect=Exception("network error"))
        with patch.dict(sys.modules, {"pywhatkit": fake_kit}):
            result = configured_messenger.send_whatsapp("John", "hi")
        assert "failed" in result.lower()


# ---------------------------------------------------------------------------
# Email tests
# ---------------------------------------------------------------------------

class TestSendEmail:
    def test_send_email_success(self, configured_messenger):
        mock_server = MagicMock()
        with patch("smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__.return_value = mock_server
            result = configured_messenger.send_email(
                "recipient@example.com", "Test Subject", "Test body"
            )
        assert "sent" in result.lower()
        mock_server.sendmail.assert_called_once()

    def test_send_email_unconfigured_returns_error(self, unconfigured_messenger):
        result = unconfigured_messenger.send_email(
            "recipient@example.com", "Subject", "Body"
        )
        assert "not configured" in result.lower() or "credentials" in result.lower()

    def test_send_email_auth_failure(self, configured_messenger):
        import smtplib
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
        with patch("smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__.return_value = mock_server
            result = configured_messenger.send_email(
                "recipient@example.com", "Subject", "Body"
            )
        assert "authentication" in result.lower() or "failed" in result.lower()

    def test_send_email_general_exception(self, configured_messenger):
        with patch("smtplib.SMTP", side_effect=Exception("connection refused")):
            result = configured_messenger.send_email(
                "recipient@example.com", "Subject", "Body"
            )
        assert "failed" in result.lower()

    def test_email_message_formatting(self, configured_messenger):
        """Verify that sendmail is called with the correct addresses."""
        mock_server = MagicMock()
        with patch("smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__.return_value = mock_server
            configured_messenger.send_email(
                "target@example.com", "Hello", "World"
            )
        call_args = mock_server.sendmail.call_args
        assert call_args[0][0] == "test@gmail.com"
        assert call_args[0][1] == "target@example.com"
