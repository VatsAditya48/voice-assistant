"""
messenger.py — Send messages via WhatsApp (pywhatkit) and Email (smtplib).

Credentials and contact mappings are read from config/settings.yaml.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

import yaml  # type: ignore

logger = logging.getLogger(__name__)

_SETTINGS_YAML = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "settings.yaml"
)


def _load_settings() -> Dict[str, Any]:
    """Load settings.yaml, returning an empty dict on failure."""
    try:
        with open(_SETTINGS_YAML, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.warning("settings.yaml not found at %s", _SETTINGS_YAML)
        return {}
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to load settings.yaml: %s", exc)
        return {}


class Messenger:
    """Send WhatsApp and Email messages."""

    def __init__(self) -> None:
        self._settings = _load_settings()

    # ------------------------------------------------------------------
    # WhatsApp
    # ------------------------------------------------------------------

    def send_whatsapp(self, contact_name: str, message: str) -> str:
        """
        Send a WhatsApp message to *contact_name*.

        The contact must have a phone-number entry in the ``whatsapp_contacts``
        section of ``settings.yaml``.

        Parameters
        ----------
        contact_name:
            The friendly name of the recipient (case-insensitive lookup).
        message:
            The text to send.

        Returns
        -------
        str
            Confirmation or error message.
        """
        contacts: Dict[str, str] = self._settings.get("whatsapp_contacts", {})

        # Case-insensitive lookup
        phone_number = None
        for name, number in contacts.items():
            if name.lower() == contact_name.lower():
                phone_number = number
                break

        if phone_number is None:
            return (
                f"Contact '{contact_name}' not found in settings.yaml. "
                "Please add their phone number under whatsapp_contacts."
            )

        try:
            import pywhatkit  # type: ignore
            from datetime import datetime, timedelta

            # Schedule 2 minutes from now to give WhatsApp Web time to open
            now = datetime.now() + timedelta(minutes=2)
            pywhatkit.sendwhatmsg(
                phone_number,
                message,
                now.hour,
                now.minute,
                wait_time=20,
                tab_close=True,
            )
            logger.info("WhatsApp message sent to %s (%s)", contact_name, phone_number)
            return f"WhatsApp message sent to {contact_name}."
        except ImportError as exc:
            return "pywhatkit is not installed. Run: pip install pywhatkit"
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("WhatsApp send failed: %s", exc)
            return f"Failed to send WhatsApp message: {exc}"

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def send_email(self, to_address: str, subject: str, body: str) -> str:
        """
        Send an email via SMTP (TLS) using credentials from settings.yaml.

        Parameters
        ----------
        to_address:
            Recipient email address.
        subject:
            Email subject line.
        body:
            Plain-text email body.

        Returns
        -------
        str
            Confirmation or error message.
        """
        email_cfg = self._settings.get("email", {})
        smtp_server = email_cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port = int(email_cfg.get("smtp_port", 587))
        sender_email = email_cfg.get("sender_email", "")
        sender_password = email_cfg.get("sender_password", "")

        if not sender_email or sender_email == "your_email@gmail.com":
            return (
                "Email credentials are not configured. "
                "Please update config/settings.yaml with your email and app password."
            )
        if not sender_password or sender_password == "your_app_password":
            return (
                "Email password is not configured. "
                "Please update config/settings.yaml with your app password."
            )

        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = to_address
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_address, msg.as_string())

            logger.info("Email sent to %s (subject: %s)", to_address, subject)
            return f"Email sent to {to_address}."
        except smtplib.SMTPAuthenticationError:
            return (
                "SMTP authentication failed. "
                "Check your email and app password in settings.yaml."
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Email send failed: %s", exc)
            return f"Failed to send email: {exc}"
