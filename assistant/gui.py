"""
gui.py — Graphical chat interface for the Friday assistant.

Provides a Tkinter-based chat window where the user can type messages or
click the microphone button to speak.  All assistant logic (intent parsing,
scheduling, app launching, …) is reused from the core ``Assistant`` class.

Launch via::

    python main.py --gui
"""

import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import scrolledtext
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (Catppuccin-Mocha inspired dark theme)
# ---------------------------------------------------------------------------
_BG = "#1e1e2e"           # main background
_BG_HEADER = "#181825"    # header / footer bar
_BG_INPUT = "#2a2a3d"     # text-entry field
_FG = "#cdd6f4"           # primary text
_FG_DIM = "#7f849c"       # timestamps / secondary text
_FG_USER = "#cba6f7"      # "You" label
_FG_BOT = "#89dceb"       # assistant name label
_ACCENT = "#cba6f7"       # Send button background
_ACCENT_HOVER = "#b4befe" # Send button hover
_BTN_MIC_IDLE = "#a6e3a1" # mic button — idle
_BTN_MIC_LIVE = "#f38ba8" # mic button — recording


class AssistantGUI:
    """Tkinter chat GUI for the Friday assistant.

    Parameters
    ----------
    handle_fn:
        ``(raw_text: str) -> str`` — accepts a user message and returns the
        assistant's reply string (or ``"__EXIT__"`` to close the window).
    listen_fn:
        Optional ``() -> str`` — records one voice utterance and returns it
        as plain text.  When *None* the microphone button is disabled.
    speak_fn:
        Optional ``(text: str) -> None`` — vocalises the assistant's reply
        via TTS.
    assistant_name:
        Display name shown in the header (default ``"Friday"``).
    """

    def __init__(
        self,
        handle_fn: Callable[[str], str],
        listen_fn: Optional[Callable[[], str]] = None,
        speak_fn: Optional[Callable[[str], None]] = None,
        assistant_name: str = "Friday",
    ) -> None:
        self._handle = handle_fn
        self._listen = listen_fn
        self._speak = speak_fn
        self._name = assistant_name
        self._mic_active = False
        self._reply_queue: queue.Queue = queue.Queue()

        self._root = tk.Tk()
        self._build_ui()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the Tk event loop (blocks until the window is closed)."""
        self._root.mainloop()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = self._root
        root.title(f"{self._name} — Chat")
        root.geometry("700x540")
        root.minsize(480, 360)
        root.configure(bg=_BG)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Fonts -------------------------------------------------------
        body_font = tkfont.Font(family="Segoe UI", size=11)
        label_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        header_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        ts_font = tkfont.Font(family="Segoe UI", size=8)
        mic_font = tkfont.Font(family="Segoe UI", size=14)
        send_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        # --- Header bar --------------------------------------------------
        header = tk.Frame(root, bg=_BG_HEADER, pady=8)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text=f"🎙️  {self._name}",
            bg=_BG_HEADER,
            fg=_FG,
            font=header_font,
            padx=14,
        ).pack(side=tk.LEFT)

        self._status_label = tk.Label(
            header,
            text="● ready",
            bg=_BG_HEADER,
            fg=_BTN_MIC_IDLE,
            font=label_font,
            padx=14,
        )
        self._status_label.pack(side=tk.RIGHT)

        # --- Chat history area -------------------------------------------
        self._chat_area = scrolledtext.ScrolledText(
            root,
            state=tk.DISABLED,
            wrap=tk.WORD,
            bg=_BG,
            fg=_FG,
            font=body_font,
            relief=tk.FLAT,
            padx=12,
            pady=10,
            spacing3=6,
            cursor="arrow",
        )
        self._chat_area.pack(fill=tk.BOTH, expand=True)

        # Text tags
        self._chat_area.tag_config("user_name", foreground=_FG_USER, font=label_font)
        self._chat_area.tag_config("bot_name", foreground=_FG_BOT, font=label_font)
        self._chat_area.tag_config("msg", foreground=_FG, font=body_font)
        self._chat_area.tag_config("ts", foreground=_FG_DIM, font=ts_font)

        # --- Input bar ---------------------------------------------------
        bottom = tk.Frame(root, bg=_BG_HEADER, pady=10, padx=10)
        bottom.pack(fill=tk.X)

        self._entry = tk.Entry(
            bottom,
            bg=_BG_INPUT,
            fg=_FG,
            insertbackground=_FG,
            font=body_font,
            relief=tk.FLAT,
            bd=0,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=8, padx=(0, 8))
        self._entry.bind("<Return>", lambda _e: self._on_send())

        send_btn = tk.Button(
            bottom,
            text="Send",
            command=self._on_send,
            bg=_ACCENT,
            fg=_BG,
            activebackground=_ACCENT_HOVER,
            activeforeground=_BG,
            font=send_font,
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        send_btn.pack(side=tk.LEFT)

        mic_state = tk.NORMAL if self._listen else tk.DISABLED
        mic_bg = _BTN_MIC_IDLE if self._listen else "#45475a"
        self._mic_btn = tk.Button(
            bottom,
            text="🎙",
            command=self._on_mic,
            bg=mic_bg,
            fg=_BG,
            activebackground=_BTN_MIC_LIVE,
            activeforeground=_BG,
            font=mic_font,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2" if self._listen else "arrow",
            state=mic_state,
        )
        self._mic_btn.pack(side=tk.LEFT, padx=(8, 0))

        # --- Initial greeting --------------------------------------------
        self._append_bot(
            f"Hello! I'm {self._name}. How can I help you? "
            "Type a message below or click 🎙 to speak."
        )
        self._entry.focus_set()

        # Poll the reply queue every 100 ms for thread-safe UI updates
        self._root.after(100, self._poll_reply_queue)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)
        self._append_user(text)
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _on_mic(self) -> None:
        if self._mic_active or self._listen is None:
            return
        self._mic_active = True
        self._mic_btn.configure(bg=_BTN_MIC_LIVE, text="⏹")
        self._set_status("● listening…", _BTN_MIC_LIVE)
        threading.Thread(target=self._listen_and_process, daemon=True).start()

    def _on_close(self) -> None:
        self._root.destroy()

    # ------------------------------------------------------------------
    # Background tasks (daemon threads — never block the UI thread)
    # ------------------------------------------------------------------

    def _listen_and_process(self) -> None:
        try:
            text = self._listen()  # type: ignore[misc]
        except Exception as exc:
            logger.error("Listen error: %s", exc)
            text = ""
        finally:
            self._reply_queue.put(("mic_done", None))

        if text:
            self._reply_queue.put(("user_msg", text))
            self._process(text)
        else:
            self._reply_queue.put(("status", ("● ready", _BTN_MIC_IDLE)))

    def _process(self, text: str) -> None:
        """Resolve intent → generate reply → optional TTS, all off the UI thread."""
        self._reply_queue.put(("status", ("● thinking…", _FG_DIM)))
        try:
            reply = self._handle(text)
        except Exception as exc:
            logger.error("Handle error: %s", exc)
            reply = "Sorry, something went wrong on my end."

        self._reply_queue.put(("bot_reply", reply))

        if self._speak and reply not in ("", "__EXIT__"):
            try:
                self._speak(reply)
            except Exception as exc:
                logger.warning("TTS error: %s", exc)

        self._reply_queue.put(("status", ("● ready", _BTN_MIC_IDLE)))

    # ------------------------------------------------------------------
    # Thread-safe UI updates — polled on the main thread
    # ------------------------------------------------------------------

    def _poll_reply_queue(self) -> None:
        try:
            while True:
                msg_type, payload = self._reply_queue.get_nowait()
                if msg_type == "bot_reply":
                    if payload == "__EXIT__":
                        self._append_bot("Goodbye! Have a great day.")
                        self._root.after(1500, self._root.destroy)
                    else:
                        self._append_bot(payload)
                elif msg_type == "user_msg":
                    self._append_user(payload)
                elif msg_type == "status":
                    label_text, color = payload
                    self._set_status(label_text, color)
                elif msg_type == "mic_done":
                    self._mic_active = False
                    self._mic_btn.configure(bg=_BTN_MIC_IDLE, text="🎙")
        except queue.Empty:
            pass
        self._root.after(100, self._poll_reply_queue)

    # ------------------------------------------------------------------
    # Chat area helpers
    # ------------------------------------------------------------------

    def _append_user(self, text: str) -> None:
        self._append_message("You", text, name_tag="user_name")

    def _append_bot(self, text: str) -> None:
        self._append_message(self._name, text, name_tag="bot_name")

    def _append_message(self, sender: str, text: str, *, name_tag: str) -> None:
        area = self._chat_area
        ts = datetime.now().strftime("%H:%M")
        area.configure(state=tk.NORMAL)
        area.insert(tk.END, f"\n{sender}  ", name_tag)
        area.insert(tk.END, f"{ts}\n", "ts")
        area.insert(tk.END, f"{text}\n", "msg")
        area.configure(state=tk.DISABLED)
        area.see(tk.END)

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.configure(text=text, fg=color)
