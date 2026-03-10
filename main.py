"""
main.py — Entry point for the Friday voice AI assistant.

Voice-only mode (default)::

    python main.py

Graphical chat window::

    python main.py --gui

In voice mode the assistant:
  1. Listens for the configured wake word.
  2. Accepts a follow-up voice command.
  3. Parses the command into an intent.
  4. Dispatches to the appropriate handler.
  5. Vocalizes the response.

In GUI mode a Tkinter chat window opens.  The user can type or click the
microphone button to speak.

Exit by saying / typing "exit", "quit", "stop", or "goodbye".
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import yaml  # type: ignore

from assistant.chat import ChatEngine
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
        chat_cfg = settings.get("chat", {})

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
        self.chat_engine = ChatEngine(
            backend=chat_cfg.get("backend", "rules"),
            ollama_model=chat_cfg.get("ollama_model", "llama3"),
            ollama_url=chat_cfg.get("ollama_url", "http://localhost:11434"),
        )

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

    def _handle(self, intent: dict, raw_text: str = "") -> str:
        """Dispatch an intent dict to the correct handler and return a reply.

        Parameters
        ----------
        intent:
            Structured intent produced by :class:`IntentParser`.
        raw_text:
            The original speech/text string.  Used as the chat prompt when
            no specific intent is matched.
        """
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

        # Anything unrecognised → conversational chat fallback
        return self.chat_engine.respond(raw_text)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run_gui(self) -> None:
        """Open the graphical chat window (Tkinter)."""
        from assistant.gui import AssistantGUI

        def handle_text(text: str) -> str:
            intent = self.parser.parse(text)
            logger.info("GUI intent: %s", intent)
            return self._handle(intent, raw_text=text)

        def listen_once() -> str:
            return self._get_listener().listen(timeout_seconds=10)

        gui = AssistantGUI(
            handle_fn=handle_text,
            listen_fn=listen_once,
            speak_fn=self.speaker.speak,
            assistant_name=self.name,
        )
        gui.run()

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

            reply = self._handle(intent, raw_text=command)

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
    parser = argparse.ArgumentParser(
        description="Friday — local voice AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py          # voice-only mode\n"
            "  python main.py --gui    # graphical chat window\n"
        ),
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the graphical chat window instead of voice-only mode.",
    )
    args = parser.parse_args()

    _configure_logging()
    assistant = Assistant()
    try:
        if args.gui:
            assistant.run_gui()
        else:
            assistant.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        assistant.scheduler.shutdown()
        if assistant._listener is not None:
            assistant._listener.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
