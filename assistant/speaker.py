"""
speaker.py — Text-to-speech module using pyttsx3 (offline).

Provides a Speaker class with a speak(text) method that vocalizes the given
text using the system's built-in TTS engine.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Speaker:
    """Text-to-speech wrapper around pyttsx3."""

    def __init__(
        self,
        rate: int = 175,
        volume: float = 1.0,
        voice_id: int = 0,
    ):
        """
        Initialize the Speaker.

        Parameters
        ----------
        rate:
            Words-per-minute speech rate (default 175).
        volume:
            Volume level between 0.0 and 1.0 (default 1.0).
        voice_id:
            Index of the system voice to use; 0 = first available (usually
            male), 1 = second (usually female).  Falls back to voice 0 if the
            requested index is out of range.
        """
        self._rate = rate
        self._volume = volume
        self._voice_id = voice_id
        self._engine = None

    def _init_engine(self) -> None:
        """Lazily initialise the pyttsx3 engine."""
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)

            voices = engine.getProperty("voices")
            if voices and self._voice_id < len(voices):
                engine.setProperty("voice", voices[self._voice_id].id)
            elif voices:
                engine.setProperty("voice", voices[0].id)
                logger.warning(
                    "Voice id %d not available; using voice 0.", self._voice_id
                )

            self._engine = engine
            logger.info("pyttsx3 TTS engine initialised.")
        except ImportError as exc:
            raise RuntimeError(
                "pyttsx3 is not installed. Run: pip install pyttsx3"
            ) from exc

    def speak(self, text: str) -> None:
        """
        Convert *text* to speech and block until the utterance is complete.

        Parameters
        ----------
        text:
            The string to vocalize.
        """
        if not text:
            return

        if self._engine is None:
            self._init_engine()

        logger.info("Speaking: %s", text)
        print(f"[Assistant]: {text}")
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("TTS error: %s", exc)

    def update_settings(
        self,
        rate: Optional[int] = None,
        volume: Optional[float] = None,
        voice_id: Optional[int] = None,
    ) -> None:
        """
        Update TTS settings at runtime.

        Only the provided keyword arguments are updated; the rest remain
        unchanged.
        """
        if self._engine is None:
            self._init_engine()

        if rate is not None:
            self._rate = rate
            self._engine.setProperty("rate", rate)

        if volume is not None:
            self._volume = volume
            self._engine.setProperty("volume", volume)

        if voice_id is not None:
            self._voice_id = voice_id
            voices = self._engine.getProperty("voices")
            if voices and voice_id < len(voices):
                self._engine.setProperty("voice", voices[voice_id].id)
