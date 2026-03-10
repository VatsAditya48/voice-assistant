"""
main.py — Entry point for the Friday voice AI assistant.

Runs a continuous listening loop that:
  1. Listens for the configured wake word.
  2. Accepts a follow-up voice command.
  3. Parses the command into an intent.
  4. Dispatches to the appropriate handler.
  5. Vocalizes the response.

Exit by saying "exit", "quit", "stop", or "goodbye".
"""

import logging
import os
import sys
from datetime import datetime

import yaml  # type: ignore

from assistant.intent_parser import IntentParser
from assistant.speaker import Speaker
from assistant.app_launcher import AppLauncher
from assistant.scheduler import Scheduler
from assistant.messenger import Messenger

logger = logging.getLogger(__name__)

_SETTINGS_YAML = os.path.join(os.path.dirname(__file__), "config", "settings.yaml")

BANNER = r"""
╔══════════════════════════════════════════════════════╗
║          🎙️  Local Voice AI Assistant                ║
║                   "Friday"                           ║
╚══════════════════════════════════════════════════════╝
"""


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_YAML, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


def _configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


class Assistant:
    """Orchestrates all assistant sub-modules."""

    def __init__(self) -> None:
        settings = _load_settings()
        assistant_cfg = settings.get("assistant", {})
        voice_cfg = settings.get("voice", {})

        self.name: str = assistant_cfg.get("name", "Friday")
        self.wake_word: str = assistant_cfg.get("wake_word", "hey friday").lower()

        self.speaker = Speaker(
            rate=voice_cfg.get("rate", 175),
            volume=voice_cfg.get("volume", 1.0),
            voice_id=voice_cfg.get("voice_id", 0),
        )
        self.parser = IntentParser()
        self.launcher = AppLauncher()
        self.scheduler = Scheduler()
        self.messenger = Messenger()

        # Listener is imported here so the rest of the assistant works even if
        # vosk / pyaudio are not installed (useful for testing).
        self._listener = None

    def _get_listener(self):
        if self._listener is None:
            from assistant.listener import Listener
            from assistant.listener import MODEL_DIR, MODEL_NAME
            settings = _load_settings()
            model_path = (
                settings.get("vosk", {}).get("model_path")
                or os.path.join(MODEL_DIR, MODEL_NAME)
            )
            self._listener = Listener(model_path=model_path)
        return self._listener

    # ------------------------------------------------------------------
    # Dispatch table
    # ------------------------------------------------------------------

    def _handle(self, intent: dict) -> str:
        """Dispatch an intent dict to the correct handler and return a reply."""
        name = intent["intent"]
        entities = intent.get("entities", {})

        if name == "greeting":
            return f"Hello! I am {self.name}. How can I help you?"

        if name == "time":
            return f"The current time is {datetime.now().strftime('%I:%M %p')}."

        if name == "date":
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

        if name == "open_app":
            return self.launcher.open_app(entities.get("app_name", ""))

        if name == "set_alarm":
            return self.scheduler.set_alarm(entities.get("time", ""))

        if name == "set_reminder":
            return self.scheduler.set_reminder(
                message=entities.get("message", ""),
                time_str=entities.get("time"),
                delta=entities.get("delta"),
                unit=entities.get("unit"),
            )

        if name == "list_alarms":
            return self.scheduler.list_alarms()

        if name == "cancel_alarm":
            return self.scheduler.cancel_alarm(entities.get("alarm_id", ""))

        if name == "send_whatsapp":
            return self.messenger.send_whatsapp(
                entities.get("contact", ""),
                entities.get("message", ""),
            )

        if name == "send_email":
            return self.messenger.send_email(
                entities.get("to", ""),
                entities.get("subject", ""),
                entities.get("body", ""),
            )

        if name == "exit":
            return "__EXIT__"

        # unknown
        return (
            "I did not understand that. Try saying something like: "
            "'open Chrome', 'set alarm for 7 AM', or 'what time is it'."
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the continuous listening loop."""
        print(BANNER)
        print(f"Assistant name : {self.name}")
        print(f"Wake word      : '{self.wake_word}'")
        print("Say the wake word to activate, then speak your command.")
        print("Say 'exit' or 'quit' to shut down.\n")

        self.speaker.speak(f"Hello! I am {self.name}. Say '{self.wake_word}' to get started.")
        listener = self._get_listener()

        while True:
            print("[Waiting for wake word …]")
            wake_text = listener.listen(timeout_seconds=30).lower()

            if not wake_text:
                continue

            if self.wake_word not in wake_text:
                # Check for direct exit command even without wake word
                if any(w in wake_text for w in ("exit", "quit", "stop", "goodbye")):
                    self._shutdown()
                    return
                continue

            print("[Wake word detected!]")
            self.speaker.speak("Yes?")

            command = listener.listen(timeout_seconds=10)
            if not command:
                self.speaker.speak("I did not catch that. Please try again.")
                continue

            print(f"[Command]: {command}")
            intent = self.parser.parse(command)
            logger.info("Intent: %s", intent)

            reply = self._handle(intent)

            if reply == "__EXIT__":
                self._shutdown()
                return

            self.speaker.speak(reply)

    def _shutdown(self) -> None:
        """Gracefully shut down all sub-modules."""
        self.speaker.speak(f"Goodbye! Have a great day.")
        print("\nShutting down …")
        self.scheduler.shutdown()
        if self._listener is not None:
            self._listener.close()
        print("Bye!")


def main() -> None:
    _configure_logging()
    assistant = Assistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        assistant.scheduler.shutdown()
        if assistant._listener is not None:
            assistant._listener.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
