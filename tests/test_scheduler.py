"""
test_scheduler.py — Unit tests for assistant/scheduler.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from assistant.scheduler import (
    Scheduler,
    _parse_clock_time,
    _parse_delta,
)


# ---------------------------------------------------------------------------
# Time parsing helpers
# ---------------------------------------------------------------------------

class TestParseClockTime:
    def test_12h_am(self):
        result = _parse_clock_time("7:30 AM")
        assert result is not None
        assert result.hour == 7
        assert result.minute == 30

    def test_12h_pm(self):
        result = _parse_clock_time("3:00 PM")
        assert result is not None
        assert result.hour == 15
        assert result.minute == 0

    def test_24h(self):
        result = _parse_clock_time("14:00")
        assert result is not None
        assert result.hour == 14

    def test_hour_only(self):
        result = _parse_clock_time("6 AM")
        assert result is not None
        assert result.hour == 6

    def test_midnight_am(self):
        result = _parse_clock_time("12:00 AM")
        assert result is not None
        assert result.hour == 0

    def test_noon_pm(self):
        result = _parse_clock_time("12:00 PM")
        assert result is not None
        assert result.hour == 12

    def test_invalid_returns_none(self):
        assert _parse_clock_time("not a time") is None

    def test_future_time_is_returned(self):
        """If the time has already passed today, it should be scheduled tomorrow."""
        past_time = (datetime.now() - timedelta(hours=1)).strftime("%I:%M %p")
        result = _parse_clock_time(past_time)
        assert result is not None
        assert result > datetime.now()


class TestParseDelta:
    def test_minutes(self):
        td = _parse_delta("in 30 minutes")
        assert td == timedelta(minutes=30)

    def test_hours(self):
        td = _parse_delta("in 2 hours")
        assert td == timedelta(hours=2)

    def test_seconds(self):
        td = _parse_delta("in 45 seconds")
        assert td == timedelta(seconds=45)

    def test_invalid_returns_none(self):
        assert _parse_delta("not a duration") is None


# ---------------------------------------------------------------------------
# Scheduler integration (mocked APScheduler)
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler_with_mock():
    """Return a Scheduler whose APScheduler backend is fully mocked."""
    sched = Scheduler()
    mock_backend = MagicMock()
    mock_backend.running = True
    mock_backend.get_jobs.return_value = []
    sched._scheduler = mock_backend
    return sched, mock_backend


class TestSchedulerSetAlarm:
    def test_set_alarm_valid(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        future = (datetime.now() + timedelta(hours=1)).strftime("%I:%M %p")
        result = sched.set_alarm(future)
        assert "alarm set" in result.lower()
        mock_backend.add_job.assert_called_once()

    def test_set_alarm_invalid_time(self, scheduler_with_mock):
        sched, _ = scheduler_with_mock
        result = sched.set_alarm("not a time")
        assert "could not" in result.lower() or "understand" in result.lower()


class TestSchedulerSetReminder:
    def test_set_reminder_absolute(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        future = (datetime.now() + timedelta(hours=1)).strftime("%I:%M %p")
        result = sched.set_reminder("call mom", time_str=future)
        assert "reminder set" in result.lower()
        mock_backend.add_job.assert_called_once()

    def test_set_reminder_relative_minutes(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        result = sched.set_reminder("take medicine", delta=30, unit="minute")
        assert "reminder set" in result.lower()
        mock_backend.add_job.assert_called_once()

    def test_set_reminder_relative_hours(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        result = sched.set_reminder("drink water", delta=2, unit="hour")
        assert "reminder set" in result.lower()

    def test_set_reminder_no_time_returns_error(self, scheduler_with_mock):
        sched, _ = scheduler_with_mock
        result = sched.set_reminder("some task")
        assert "please specify" in result.lower() or "could not" in result.lower()


class TestSchedulerListAlarms:
    def test_list_empty(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        mock_backend.get_jobs.return_value = []
        result = sched.list_alarms()
        assert "no alarms" in result.lower()

    def test_list_with_jobs(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        job = MagicMock()
        job.id = "job_1"
        job.next_run_time = datetime.now() + timedelta(hours=1)
        mock_backend.get_jobs.return_value = [job]
        sched._jobs["job_1"] = "Alarm at 08:00 AM"
        result = sched.list_alarms()
        assert "job_1" in result


class TestSchedulerCancelAlarm:
    def test_cancel_existing(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        sched._jobs["job_1"] = "Test alarm"
        result = sched.cancel_alarm("job_1")
        assert "cancelled" in result.lower()
        mock_backend.remove_job.assert_called_with("job_1")

    def test_cancel_nonexistent(self, scheduler_with_mock):
        sched, mock_backend = scheduler_with_mock
        mock_backend.remove_job.side_effect = Exception("Job not found")
        result = sched.cancel_alarm("nonexistent_id")
        assert "could not" in result.lower()
