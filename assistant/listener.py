"""
listener.py — Speech-to-text module using Vosk (offline).

Listens from the default microphone and returns recognized text as a string.
Auto-downloads the small English Vosk model if not present.
"""

import json
import logging
import os
import urllib.request
import zipfile

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
)
MODEL_DIR = "models"
MODEL_NAME = "vosk-model-small-en-us-0.15"


def _download_model(model_path: str) -> None:
    """Download and extract the Vosk model if it is not already present."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    zip_path = os.path.join(MODEL_DIR, f"{MODEL_NAME}.zip")
    logger.info("Downloading Vosk model — this may take a minute …")
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(MODEL_DIR)
    os.remove(zip_path)
    logger.info("Vosk model downloaded and extracted to %s", model_path)


class Listener:
    """Microphone → text using the Vosk offline speech recognition engine."""

    def __init__(self, model_path: str = os.path.join(MODEL_DIR, MODEL_NAME)):
        """
        Initialize the Listener.

        Parameters
        ----------
        model_path:
            Path to the Vosk model directory.  The model is downloaded
            automatically if the directory does not exist.
        """
        self._model_path = model_path
        self._model = None
        self._recognizer = None
        self._pyaudio = None
        self._stream = None
        self._sample_rate = 16000
        self._chunk = 4000

    def _ensure_model(self) -> None:
        """Download the Vosk model if it is not already on disk."""
        if not os.path.isdir(self._model_path):
            _download_model(self._model_path)

    def _load_model(self) -> None:
        """Lazily import Vosk and load the model."""
        try:
            from vosk import KaldiRecognizer, Model  # type: ignore

            self._ensure_model()
            self._model = Model(self._model_path)
            self._recognizer = KaldiRecognizer(self._model, self._sample_rate)
            logger.info("Vosk model loaded from %s", self._model_path)
        except ImportError as exc:
            raise RuntimeError(
                "vosk is not installed. Run: pip install vosk"
            ) from exc

    def _open_stream(self) -> None:
        """Open the PyAudio microphone stream."""
        try:
            import pyaudio  # type: ignore

            self._pyaudio = pyaudio.PyAudio()
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk,
            )
            self._stream.start_stream()
        except ImportError as exc:
            raise RuntimeError(
                "pyaudio is not installed. Run: pip install pyaudio"
            ) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError(
                f"Could not open microphone stream: {exc}"
            ) from exc

    def listen(self, timeout_seconds: int = 10) -> str:
        """
        Listen from the microphone and return the recognized text.

        Parameters
        ----------
        timeout_seconds:
            Maximum number of seconds to wait for speech before giving up.

        Returns
        -------
        str
            The recognized text, or an empty string if nothing was heard.
        """
        if self._model is None:
            self._load_model()
        if self._stream is None:
            self._open_stream()

        logger.info("Listening …")
        chunks_per_second = self._sample_rate // self._chunk
        max_chunks = timeout_seconds * chunks_per_second

        for _ in range(max_chunks):
            try:
                data = self._stream.read(self._chunk, exception_on_overflow=False)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Microphone read error: %s", exc)
                break

            if self._recognizer.AcceptWaveform(data):
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    logger.info("Recognized: %s", text)
                    return text

        # Return partial result if available
        partial = json.loads(self._recognizer.FinalResult())
        return partial.get("text", "").strip()

    def close(self) -> None:
        """Release audio resources."""
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio is not None:
            self._pyaudio.terminate()
            self._pyaudio = None
