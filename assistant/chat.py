"""
chat.py — Conversational chat engine for the Friday assistant.

Provides a ChatEngine that responds to general conversation and questions.
Works fully offline using rule-based pattern matching.  Optionally delegates
to a locally-running Ollama LLM when configured in settings.yaml under the
``chat:`` key.
"""

import ast
import logging
import operator
import random
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule-based response table
# Each entry: (compiled regex, list of possible responses)
# An *empty* response list is a sentinel that triggers the math evaluator.
# ---------------------------------------------------------------------------

_RULES: List[Tuple[re.Pattern, List[str]]] = [
    # How are you
    (
        re.compile(
            r"\b(how\s+are\s+you|how\s*(\'re|\s+are)\s+you\s+doing"
            r"|how\s+do\s+you\s+feel|you\s+okay)\b",
            re.I,
        ),
        [
            "I'm doing great, thanks for asking! How about you?",
            "I'm functioning perfectly! Ready to help.",
            "All systems go! Thanks for checking in.",
        ],
    ),
    # Who / what are you
    (
        re.compile(r"\b(who|what)\s+are\s+you\b", re.I),
        [
            "I'm Friday, your local offline voice AI assistant. "
            "I can open apps, set alarms, send messages, and chat with you!"
        ],
    ),
    # What can you do
    (
        re.compile(
            r"\bwhat\s+can\s+you\s+do\b"
            r"|\bwhat\s+are\s+your\s+(capabilities|features|skills)\b",
            re.I,
        ),
        [
            "I can open applications, set alarms and reminders, send WhatsApp "
            "messages and emails, tell you the time and date, and chat with you. "
            "Just ask!"
        ],
    ),
    # Tell me a joke
    (
        re.compile(
            r"\b(tell\s+(me\s+)?a?\s*joke"
            r"|say\s+something\s+funny"
            r"|make\s+me\s+laugh)\b",
            re.I,
        ),
        [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "I tried to come up with a joke about AI, but I was worried it might go over your head.",
            "Why did the computer keep sneezing? It had a virus!",
            "What do you call a computer that sings? A Dell!",
            "I would tell you a UDP joke, but you might not get it.",
        ],
    ),
    # Favorite color / food / etc.
    (
        re.compile(
            r"\bfavorite\s+(color|colour|animal|food|movie|song|book)\b",
            re.I,
        ),
        [
            "As an AI, I don't have personal preferences — but I'm happy to talk about yours!",
            "I don't experience the world that way, but I'd love to hear what yours is!",
        ],
    ),
    # Are you human / robot / AI
    (
        re.compile(
            r"\bare\s+you\s+(human|a\s+robot|an?\s+ai|a\s+bot|real|alive|sentient)\b",
            re.I,
        ),
        [
            "I'm an AI assistant — not human, but here to help!",
            "Proudly artificial! I'm Friday, your voice assistant.",
        ],
    ),
    # Thank you
    (
        re.compile(r"\b(thank\s+you|thanks|thank\s+u|cheers)\b", re.I),
        [
            "You're welcome! Anything else I can help with?",
            "Happy to help! Let me know if you need anything else.",
            "Anytime!",
        ],
    ),
    # Weather (not supported offline)
    (
        re.compile(
            r"\b(weather|forecast|temperature|rain|sunny|cloudy)\b",
            re.I,
        ),
        [
            "I don't have access to live weather data right now. "
            "Try checking a weather app or website!"
        ],
    ),
    # News
    (
        re.compile(
            r"\b(news|headlines|latest\s+news|what\s*('?s|\s+is)\s+happening)\b",
            re.I,
        ),
        [
            "I don't have internet access to fetch live news. "
            "You could check a news website or app for the latest updates!"
        ],
    ),
    # Math — empty responses list signals ChatEngine to call _try_math()
    (
        re.compile(
            r"\b(what\s+is|calculate|compute|solve)\s+[\d\s\+\-\*\/\.\(\)x×÷]+",
            re.I,
        ),
        [],
    ),
    # Meaning of life
    (
        re.compile(r"\b(meaning|purpose)\s+of\s+(life|existence)\b", re.I),
        ["42. At least, that's what I've heard."],
    ),
    # Fun fact
    (
        re.compile(
            r"\b(fun\s+fact|interesting\s+fact"
            r"|tell\s+me\s+something\s+(interesting|cool|fun))\b",
            re.I,
        ),
        [
            "Did you know honey never spoils? Archaeologists have found "
            "3,000-year-old honey in Egyptian tombs that was still edible!",
            "A group of flamingos is called a flamboyance. How fitting!",
            "Octopuses have three hearts and blue blood!",
            "The Eiffel Tower can be 15 cm taller during summer due to thermal expansion.",
        ],
    ),
    # General what-is / who-is (low-priority catch-all — keep last)
    (
        re.compile(r"\b(what\s+is|who\s+is|tell\s+me\s+about)\s+\S+", re.I),
        [
            "That's an interesting question! I'm running fully offline, so I don't "
            "have access to a knowledge base right now. "
            "Try asking me to open a browser to look it up!"
        ],
    ),
]

# Fallback responses when no rule matches
_FALLBACKS = [
    "I'm not sure I understood that. Could you rephrase?",
    "Hmm, I don't have a great answer for that. "
    "Try asking me to open an app or set an alarm!",
    "I'm still learning! I didn't quite get that.",
    "I'm not sure about that one. Is there something else I can help you with?",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_eval(expr: str) -> Optional[float]:
    """Evaluate a simple arithmetic expression using the AST — no eval().

    Only the four basic binary operators (+, -, *, /) and unary minus are
    allowed.  Returns *None* if the expression is malformed or unsupported.
    """
    _BINOPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval_node(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
        raise ValueError(f"Unsupported node: {ast.dump(node)}")

    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
        # Return int representation when result is a whole number
        return int(result) if result == int(result) else result
    except Exception:
        return None


def _try_math(text: str) -> Optional[str]:
    """Evaluate a simple arithmetic expression embedded in *text*."""
    m = re.search(
        r"\b(?:what\s+is|calculate|compute|solve)\s+([\d\s\+\-\*\/\.\(\)x×÷]+)",
        text,
        re.I,
    )
    if not m:
        return None

    expr = m.group(1).strip()
    # Normalise written operators
    expr = re.sub(r"\s*[xX×]\s*", "*", expr)
    expr = re.sub(r"\s*÷\s*", "/", expr)
    # Remove any whitespace between tokens so the AST parser is happy
    expr = re.sub(r"\s+", "", expr)

    # Reject if any unexpected characters remain
    if not re.fullmatch(r"[\d\+\-\*\/\.\(\)]+", expr):
        return None

    result = _safe_eval(expr)
    if result is None:
        return None
    return f"The answer is {result}."


# ---------------------------------------------------------------------------
# ChatEngine
# ---------------------------------------------------------------------------


class ChatEngine:
    """Conversational engine for the Friday assistant.

    By default uses rule-based pattern matching (``backend='rules'``).
    When ``backend='ollama'`` is set in *settings.yaml* under the ``chat:``
    key the engine forwards messages to a locally-running Ollama instance
    and falls back to rules if the request fails.

    Parameters
    ----------
    backend:
        ``'rules'`` (default) or ``'ollama'``.
    ollama_model:
        Ollama model name, e.g. ``'llama3'`` (used only when
        ``backend='ollama'``).
    ollama_url:
        Base URL of the Ollama REST API (default ``http://localhost:11434``).
    """

    def __init__(
        self,
        backend: str = "rules",
        ollama_model: str = "llama3",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self._backend = backend.lower()
        self._ollama_model = ollama_model
        self._ollama_url = ollama_url.rstrip("/")
        self._history: List[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def respond(self, text: str) -> str:
        """Return a conversational reply to *text*."""
        text = text.strip()
        if not text:
            return "I didn't catch that. Could you say that again?"

        if self._backend == "ollama":
            reply = self._ollama_respond(text)
        else:
            reply = self._rules_respond(text)

        self._history.append({"role": "user", "content": text})
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset_history(self) -> None:
        """Clear the conversation history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _rules_respond(self, text: str) -> str:
        for pattern, responses in _RULES:
            if pattern.search(text):
                if not responses:           # math sentinel
                    answer = _try_math(text)
                    if answer:
                        return answer
                    continue                # keep trying other rules
                return random.choice(responses)
        return random.choice(_FALLBACKS)

    def _ollama_respond(self, text: str) -> str:
        """Send *text* to a local Ollama instance and return its reply."""
        try:
            import json
            import urllib.request

            messages = list(self._history) + [{"role": "user", "content": text}]
            payload = json.dumps(
                {
                    "model": self._ollama_model,
                    "messages": messages,
                    "stream": False,
                }
            ).encode()
            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                data = json.loads(resp.read())
                return data["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Ollama request failed (%s); falling back to rules.", exc)
            return self._rules_respond(text)
