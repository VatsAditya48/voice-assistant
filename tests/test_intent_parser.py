"""
test_intent_parser.py — Unit tests for assistant/intent_parser.py
"""

import pytest
from assistant.intent_parser import IntentParser


@pytest.fixture
def parser():
    return IntentParser()


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------

class TestGreeting:
    def test_hello(self, parser):
        result = parser.parse("hello")
        assert result["intent"] == "greeting"

    def test_hi(self, parser):
        result = parser.parse("hi")
        assert result["intent"] == "greeting"

    def test_good_morning(self, parser):
        result = parser.parse("good morning")
        assert result["intent"] == "greeting"


# ---------------------------------------------------------------------------
# Exit
# ---------------------------------------------------------------------------

class TestExit:
    def test_exit(self, parser):
        assert parser.parse("exit")["intent"] == "exit"

    def test_quit(self, parser):
        assert parser.parse("quit")["intent"] == "exit"

    def test_stop(self, parser):
        assert parser.parse("stop")["intent"] == "exit"

    def test_goodbye(self, parser):
        assert parser.parse("goodbye")["intent"] == "exit"


# ---------------------------------------------------------------------------
# Time / Date
# ---------------------------------------------------------------------------

class TestTimeDate:
    def test_what_time_is_it(self, parser):
        assert parser.parse("what time is it")["intent"] == "time"

    def test_tell_me_the_time(self, parser):
        assert parser.parse("tell me the time")["intent"] == "time"

    def test_what_is_the_date(self, parser):
        assert parser.parse("what is today's date")["intent"] == "date"

    def test_date_shorthand(self, parser):
        assert parser.parse("what's the date")["intent"] == "date"


# ---------------------------------------------------------------------------
# Open app
# ---------------------------------------------------------------------------

class TestOpenApp:
    def test_open_chrome(self, parser):
        result = parser.parse("open chrome")
        assert result["intent"] == "open_app"
        assert result["entities"]["app_name"] == "chrome"

    def test_launch_notepad(self, parser):
        result = parser.parse("launch notepad")
        assert result["intent"] == "open_app"
        assert result["entities"]["app_name"] == "notepad"

    def test_start_spotify(self, parser):
        result = parser.parse("start spotify")
        assert result["intent"] == "open_app"
        assert result["entities"]["app_name"] == "spotify"

    def test_open_vs_code(self, parser):
        result = parser.parse("open vs code")
        assert result["intent"] == "open_app"
        assert "vs code" in result["entities"]["app_name"] or "code" in result["entities"]["app_name"]


# ---------------------------------------------------------------------------
# Set alarm
# ---------------------------------------------------------------------------

class TestSetAlarm:
    def test_set_alarm_with_ampm(self, parser):
        result = parser.parse("set alarm for 7:30 AM")
        assert result["intent"] == "set_alarm"
        assert "7:30" in result["entities"]["time"]

    def test_wake_me_up_at(self, parser):
        result = parser.parse("wake me up at 6 AM")
        assert result["intent"] == "set_alarm"
        assert "6" in result["entities"]["time"]

    def test_set_alarm_24h(self, parser):
        result = parser.parse("set alarm at 14:00")
        assert result["intent"] == "set_alarm"
        assert "14:00" in result["entities"]["time"]


# ---------------------------------------------------------------------------
# Set reminder
# ---------------------------------------------------------------------------

class TestSetReminder:
    def test_remind_at_time(self, parser):
        result = parser.parse("remind me to call mom at 5 PM")
        assert result["intent"] == "set_reminder"
        assert "call mom" in result["entities"]["message"]
        assert "5" in result["entities"]["time"]

    def test_remind_in_minutes(self, parser):
        result = parser.parse("remind me to take medicine in 30 minutes")
        assert result["intent"] == "set_reminder"
        assert "take medicine" in result["entities"]["message"]
        assert result["entities"]["delta"] == 30
        assert result["entities"]["unit"] == "minute"

    def test_remind_in_hours(self, parser):
        result = parser.parse("remind me to call john in 2 hours")
        assert result["intent"] == "set_reminder"
        assert result["entities"]["delta"] == 2
        assert result["entities"]["unit"] == "hour"


# ---------------------------------------------------------------------------
# Send WhatsApp
# ---------------------------------------------------------------------------

class TestSendWhatsApp:
    def test_send_whatsapp(self, parser):
        result = parser.parse("send whatsapp message to John saying hello there")
        assert result["intent"] == "send_whatsapp"
        assert result["entities"]["contact"] == "John"
        assert "hello there" in result["entities"]["message"]

    def test_send_whatsapp_no_message_keyword(self, parser):
        result = parser.parse("send whatsapp to Mom saying I'll be late")
        assert result["intent"] == "send_whatsapp"
        assert result["entities"]["contact"] == "Mom"


# ---------------------------------------------------------------------------
# Send email
# ---------------------------------------------------------------------------

class TestSendEmail:
    def test_send_email(self, parser):
        result = parser.parse(
            "send email to john@example.com subject meeting body see you at 3"
        )
        assert result["intent"] == "send_email"
        assert result["entities"]["to"] == "john@example.com"
        assert "meeting" in result["entities"]["subject"]
        assert "see you at 3" in result["entities"]["body"]


# ---------------------------------------------------------------------------
# List / cancel alarms
# ---------------------------------------------------------------------------

class TestAlarmManagement:
    def test_list_alarms(self, parser):
        assert parser.parse("list all alarms")["intent"] == "list_alarms"

    def test_show_reminders(self, parser):
        assert parser.parse("show reminders")["intent"] == "list_alarms"

    def test_cancel_alarm(self, parser):
        result = parser.parse("cancel alarm job_1")
        assert result["intent"] == "cancel_alarm"
        assert result["entities"]["alarm_id"] == "job_1"


# ---------------------------------------------------------------------------
# Unknown / empty
# ---------------------------------------------------------------------------

class TestUnknown:
    def test_empty_string(self, parser):
        assert parser.parse("")["intent"] == "unknown"

    def test_gibberish(self, parser):
        assert parser.parse("blah blah blah xyz")["intent"] == "unknown"
