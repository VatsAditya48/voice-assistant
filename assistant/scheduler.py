"""
scheduler.py — Alarms and reminders using APScheduler + win10toast.

Supports:
  * set_alarm(time_str)                     — trigger at a clock time
  * set_reminder(message, time_str|minutes) — trigger with a custom message
  * list_alarms()                           — list active jobs
  * cancel_alarm(alarm_id)                  — remove a scheduled job
"""

import logging
import platform
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper — parse time strings
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?",
    re.IGNORECASE,
)
_DELTA_RE = re.compile(r"in\s+(?P<delta>\d+)\s+(?P<unit>minutes?|hours?|seconds?)", re.IGNORECASE)


def _parse_clock_time(time_str: str) -> Optional[datetime]:
    """
    Convert a string like "7:30 AM", "14:00", or "6" into the next
    occurrence of that wall clock time (today or tomorrow).

    Returns None if the string cannot be parsed.
    """
    m = _TIME_RE.match(time_str.strip())
    if not m:
        return None

    hour = int(m.group("hour"))
    minute = int(m.group("minute") or 0)
    ampm = (m.group("ampm") or "").lower()

    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    now = datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _parse_delta(time_str: str) -> Optional[timedelta]:
    """Parse "in 30 minutes" / "in 2 hours" into a timedelta, or None."""
    m = _DELTA_RE.search(time_str)
    if not m:
        return None
    delta = int(m.group("delta"))
    unit = m.group("unit").rstrip("s")
    if unit == "minute":
        return timedelta(minutes=delta)
    if unit == "hour":
        return timedelta(hours=delta)
    if unit == "second":
        return timedelta(seconds=delta)
    return None


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------

def _notify(title: str, message: str) -> None:
    """Show a desktop notification (Windows) or log a fallback message."""
    if platform.system() == "Windows":
        try:
            from win10toast import ToastNotifier  # type: ignore

            ToastNotifier().show_toast(title, message, duration=10, threaded=True)
            return
        except ImportError:
            logger.warning("win10toast not installed; falling back to console.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Toast notification failed: %s", exc)

    # Fallback for non-Windows or missing library
    print(f"\n🔔 {title}: {message}")


def _play_alarm_sound() -> None:
    """Play a system beep on Windows, or print a bell char elsewhere."""
    if platform.system() == "Windows":
        try:
            import winsound  # type: ignore  # Windows-only stdlib module

            winsound.Beep(1000, 1500)
            return
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("winsound failed: %s", exc)
    print("\a", end="", flush=True)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """Manage alarms and reminders via APScheduler."""

    def __init__(self) -> None:
        self._scheduler = None
        self._jobs: Dict[str, str] = {}  # job_id → human label
        self._counter = 0

    def _ensure_started(self) -> None:
        """Lazily initialise and start the APScheduler BackgroundScheduler."""
        if self._scheduler is not None:
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore

            self._scheduler = BackgroundScheduler()
            self._scheduler.start()
            logger.info("APScheduler started.")
        except ImportError as exc:
            raise RuntimeError(
                "APScheduler is not installed. Run: pip install APScheduler"
            ) from exc

    def _next_id(self) -> str:
        self._counter += 1
        return f"job_{self._counter}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_alarm(self, time_str: str) -> str:
        """
        Schedule an alarm at the wall clock time described by *time_str*.

        Parameters
        ----------
        time_str:
            A string such as ``"7:30 AM"``, ``"14:00"``, or ``"6"``.

        Returns
        -------
        str
            Confirmation or error message.
        """
        self._ensure_started()
        run_at = _parse_clock_time(time_str)
        if run_at is None:
            return f"Sorry, I could not understand the time '{time_str}'."

        job_id = self._next_id()
        label = f"Alarm at {run_at.strftime('%I:%M %p')}"
        self._scheduler.add_job(
            _alarm_callback,
            "date",
            run_date=run_at,
            id=job_id,
            args=[label],
        )
        self._jobs[job_id] = label
        logger.info("Alarm scheduled: %s (id=%s)", label, job_id)
        return f"Alarm set for {run_at.strftime('%I:%M %p')}."

    def set_reminder(
        self,
        message: str,
        time_str: Optional[str] = None,
        delta: Optional[int] = None,
        unit: Optional[str] = None,
    ) -> str:
        """
        Schedule a reminder.

        Supply either *time_str* (absolute clock time) **or** *delta* + *unit*
        (relative offset).

        Parameters
        ----------
        message:
            The reminder text shown in the notification.
        time_str:
            Absolute target time, e.g. ``"5 PM"``.
        delta:
            Number of time units from now.
        unit:
            One of ``"minute"``, ``"hour"``, ``"second"``.

        Returns
        -------
        str
            Confirmation or error message.
        """
        self._ensure_started()

        if time_str:
            run_at = _parse_clock_time(time_str)
            if run_at is None:
                return f"Sorry, I could not understand the time '{time_str}'."
        elif delta is not None and unit:
            td = _parse_delta(f"in {delta} {unit}s")
            if td is None:
                return "Sorry, I could not parse the reminder time."
            run_at = datetime.now() + td
        else:
            return "Please specify a time or a duration for the reminder."

        job_id = self._next_id()
        label = f"Reminder: {message}"
        self._scheduler.add_job(
            _reminder_callback,
            "date",
            run_date=run_at,
            id=job_id,
            args=[message],
        )
        self._jobs[job_id] = label
        logger.info("Reminder scheduled: %r at %s (id=%s)", message, run_at, job_id)
        return f"Reminder set for {run_at.strftime('%I:%M %p')}: '{message}'."

    def list_alarms(self) -> str:
        """Return a human-readable list of all active alarms/reminders."""
        self._ensure_started()
        jobs = self._scheduler.get_jobs()
        if not jobs:
            return "No alarms or reminders are currently scheduled."
        lines = ["Active alarms and reminders:"]
        for job in jobs:
            label = self._jobs.get(job.id, job.id)
            next_run = job.next_run_time
            time_str = next_run.strftime("%Y-%m-%d %I:%M %p") if next_run else "unknown"
            lines.append(f"  [{job.id}] {label} — {time_str}")
        return "\n".join(lines)

    def cancel_alarm(self, alarm_id: str) -> str:
        """
        Cancel the alarm or reminder identified by *alarm_id*.

        Parameters
        ----------
        alarm_id:
            The job ID string returned by :meth:`list_alarms`.

        Returns
        -------
        str
            Confirmation or error message.
        """
        self._ensure_started()
        try:
            self._scheduler.remove_job(alarm_id)
            label = self._jobs.pop(alarm_id, alarm_id)
            logger.info("Cancelled job %s (%s)", alarm_id, label)
            return f"Cancelled: {label}."
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Could not cancel job %s: %s", alarm_id, exc)
            return f"Could not cancel alarm '{alarm_id}'. Is the ID correct?"

    def shutdown(self) -> None:
        """Stop the background scheduler gracefully."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")


# ---------------------------------------------------------------------------
# Callbacks executed by APScheduler (must be module-level functions)
# ---------------------------------------------------------------------------

def _alarm_callback(label: str) -> None:
    """Triggered when an alarm fires."""
    _play_alarm_sound()
    _notify("⏰ Alarm", label)
    print(f"\n⏰ {label}")


def _reminder_callback(message: str) -> None:
    """Triggered when a reminder fires."""
    _play_alarm_sound()
    _notify("🔔 Reminder", message)
    print(f"\n🔔 Reminder: {message}")
