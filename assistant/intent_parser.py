"""
intent_parser.py — Parse natural language commands into structured intents.

Uses regex patterns and keyword matching to classify user input into one of
the supported intents and extract relevant entities.
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
Intent = Dict[str, Any]


def _make_result(intent: str, **entities: Any) -> Intent:
    return {"intent": intent, "entities": entities}


# ---------------------------------------------------------------------------
# Pattern definitions (order matters — more specific patterns first)
# ---------------------------------------------------------------------------

# Greeting
_GREETING_PATTERNS = re.compile(
    r"^\s*(hello|hi|hey|good\s*(morning|afternoon|evening|night))\b",
    re.IGNORECASE,
)

# Exit
_EXIT_PATTERNS = re.compile(
    r"\b(exit|quit|stop|goodbye|bye|shut\s*down)\b",
    re.IGNORECASE,
)

# Time query
_TIME_PATTERNS = re.compile(
    r"\b(what(\'?s|\s+is)\s+(the\s+)?time|what\s+time\s+is\s+it|tell\s+me\s+the\s+time|current\s+time)\b",
    re.IGNORECASE,
)

# Date query
_DATE_PATTERNS = re.compile(
    r"\b(what(\'?s|\s+is)\s+(the\s+|today\'?s?\s+)?date|today\'?s?\s+date|what\s+day\s+is\s+it)\b",
    re.IGNORECASE,
)

# Open app — "open chrome", "launch notepad", "start spotify", "run calc"
_OPEN_APP_PATTERN = re.compile(
    r"\b(open|launch|start|run|execute)\s+(?P<app_name>[a-zA-Z0-9\s_\-]+?)(\s+(app|application|program|software))?\s*$",
    re.IGNORECASE,
)

# Set alarm — "set alarm for 7:30 AM", "wake me up at 6", "set alarm at 14:00"
_SET_ALARM_PATTERN = re.compile(
    r"\b(set\s+alarm(\s+for)?|wake\s+me\s+up\s+at|alarm\s+at)\s+(?P<time>[\d:]+\s*(am|pm)?)",
    re.IGNORECASE,
)

# Set reminder — "remind me to X in 30 minutes / at 5 PM"
_SET_REMINDER_AT_PATTERN = re.compile(
    r"\bremind\s+me\s+(to\s+)?(?P<message>.+?)\s+at\s+(?P<time>[\d:]+\s*(am|pm)?)\s*$",
    re.IGNORECASE,
)
_SET_REMINDER_IN_PATTERN = re.compile(
    r"\bremind\s+me\s+(to\s+)?(?P<message>.+?)\s+in\s+(?P<delta>\d+)\s+(?P<unit>minutes?|hours?|seconds?)\s*$",
    re.IGNORECASE,
)

# Send WhatsApp — "send whatsapp message to John saying hello"
_WHATSAPP_PATTERN = re.compile(
    r"\bsend\s+(a\s+)?whatsapp(\s+message)?\s+to\s+(?P<contact>[a-zA-Z\s]+?)\s+(saying|:)\s+(?P<message>.+?)\s*$",
    re.IGNORECASE,
)

# Send email — "send email to john@example.com subject meeting body see you at 3"
_EMAIL_PATTERN = re.compile(
    r"\bsend\s+(an?\s+)?email\s+to\s+(?P<to>\S+@\S+)\s+subject\s+(?P<subject>.+?)\s+body\s+(?P<body>.+?)\s*$",
    re.IGNORECASE,
)

# List alarms
_LIST_ALARMS_PATTERN = re.compile(
    r"\b(list|show)\s+(all\s+)?(alarms?|reminders?)\b",
    re.IGNORECASE,
)

# Cancel alarm — "cancel alarm 1", "cancel reminder 2"
_CANCEL_ALARM_PATTERN = re.compile(
    r"\bcancel\s+(alarm|reminder)\s+(?P<alarm_id>\S+)",
    re.IGNORECASE,
)


class IntentParser:
    """Parse a natural language command into a structured intent dict."""

    def parse(self, text: str) -> Intent:
        """
        Parse *text* and return a dict with keys ``intent`` and ``entities``.

        Parameters
        ----------
        text:
            The recognised speech string to classify.

        Returns
        -------
        dict
            ``{"intent": <str>, "entities": {<str>: <Any>}}``
        """
        if not text:
            return _make_result("unknown")

        text = text.strip()
        logger.debug("Parsing: %r", text)

        # Exit
        if _EXIT_PATTERNS.search(text):
            return _make_result("exit")

        # Greeting
        if _GREETING_PATTERNS.search(text):
            return _make_result("greeting")

        # Time
        if _TIME_PATTERNS.search(text):
            return _make_result("time")

        # Date
        if _DATE_PATTERNS.search(text):
            return _make_result("date")

        # List alarms
        if _LIST_ALARMS_PATTERN.search(text):
            return _make_result("list_alarms")

        # Cancel alarm
        m = _CANCEL_ALARM_PATTERN.search(text)
        if m:
            return _make_result("cancel_alarm", alarm_id=m.group("alarm_id"))

        # Set alarm
        m = _SET_ALARM_PATTERN.search(text)
        if m:
            return _make_result("set_alarm", time=m.group("time").strip())

        # Set reminder (at a specific time)
        m = _SET_REMINDER_AT_PATTERN.search(text)
        if m:
            return _make_result(
                "set_reminder",
                message=m.group("message").strip(),
                time=m.group("time").strip(),
                delta=None,
                unit=None,
            )

        # Set reminder (in X minutes/hours)
        m = _SET_REMINDER_IN_PATTERN.search(text)
        if m:
            return _make_result(
                "set_reminder",
                message=m.group("message").strip(),
                time=None,
                delta=int(m.group("delta")),
                unit=m.group("unit").rstrip("s"),  # normalise to singular
            )

        # Send WhatsApp
        m = _WHATSAPP_PATTERN.search(text)
        if m:
            return _make_result(
                "send_whatsapp",
                contact=m.group("contact").strip(),
                message=m.group("message").strip(),
            )

        # Send email
        m = _EMAIL_PATTERN.search(text)
        if m:
            return _make_result(
                "send_email",
                to=m.group("to").strip(),
                subject=m.group("subject").strip(),
                body=m.group("body").strip(),
            )

        # Open app (checked last so "send" / "set" commands don't match)
        m = _OPEN_APP_PATTERN.search(text)
        if m:
            return _make_result(
                "open_app", app_name=m.group("app_name").strip().lower()
            )

        return _make_result("unknown")
