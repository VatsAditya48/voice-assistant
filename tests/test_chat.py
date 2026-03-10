"""
test_chat.py — Unit tests for assistant/chat.py
"""

import pytest
from unittest.mock import patch, MagicMock
from assistant.chat import ChatEngine, _try_math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return ChatEngine(backend="rules")


# ---------------------------------------------------------------------------
# _try_math helper
# ---------------------------------------------------------------------------

class TestTryMath:
    def test_addition(self):
        assert _try_math("what is 2 + 3") == "The answer is 5."

    def test_multiplication_x(self):
        result = _try_math("calculate 4 x 5")
        assert result == "The answer is 20."

    def test_subtraction(self):
        result = _try_math("what is 10 - 3")
        assert result == "The answer is 7."

    def test_division(self):
        result = _try_math("compute 9 / 3")
        assert result is not None
        assert "3" in result

    def test_no_expression_returns_none(self):
        assert _try_math("what is the weather") is None

    def test_unsafe_expression_returns_none(self):
        # Contains letters that aren't operators — must be rejected
        assert _try_math("calculate import os") is None


# ---------------------------------------------------------------------------
# Rule-based responses
# ---------------------------------------------------------------------------

class TestRulesBackend:
    def test_how_are_you(self, engine):
        reply = engine.respond("how are you")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_who_are_you(self, engine):
        reply = engine.respond("who are you")
        assert "friday" in reply.lower() or "assistant" in reply.lower()

    def test_what_can_you_do(self, engine):
        reply = engine.respond("what can you do")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_tell_me_a_joke(self, engine):
        reply = engine.respond("tell me a joke")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_thank_you(self, engine):
        reply = engine.respond("thank you")
        assert "welcome" in reply.lower() or "happy" in reply.lower() or "anytime" in reply.lower()

    def test_weather_fallback(self, engine):
        reply = engine.respond("what's the weather like today")
        assert "weather" in reply.lower() or "internet" in reply.lower()

    def test_news_fallback(self, engine):
        reply = engine.respond("what's in the news")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_math_via_chat(self, engine):
        reply = engine.respond("what is 6 + 7")
        assert "13" in reply

    def test_meaning_of_life(self, engine):
        reply = engine.respond("what is the meaning of life")
        assert "42" in reply

    def test_fun_fact(self, engine):
        reply = engine.respond("tell me a fun fact")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_are_you_human(self, engine):
        reply = engine.respond("are you human")
        assert "ai" in reply.lower() or "artificial" in reply.lower()

    def test_favorite_color(self, engine):
        reply = engine.respond("what's your favorite color")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_unknown_falls_back_to_reply(self, engine):
        # Completely unrecognised text should still return a non-empty string
        reply = engine.respond("xyzzy plugh frobozz")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_empty_text(self, engine):
        reply = engine.respond("")
        assert "catch" in reply.lower() or "say" in reply.lower()


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_grows(self, engine):
        engine.respond("hello")
        assert len(engine._history) == 2  # user + assistant

    def test_reset_history(self, engine):
        engine.respond("hello")
        engine.reset_history()
        assert engine._history == []


# ---------------------------------------------------------------------------
# Ollama backend (mocked — no real HTTP call)
# ---------------------------------------------------------------------------

class TestOllamaBackend:
    def _make_engine(self):
        return ChatEngine(
            backend="ollama",
            ollama_model="llama3",
            ollama_url="http://localhost:11434",
        )

    def test_ollama_returns_content(self):
        engine = self._make_engine()
        fake_response = b'{"message": {"content": "Hello from Ollama!"}}'

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            reply = engine.respond("say hello")

        assert reply == "Hello from Ollama!"

    def test_ollama_falls_back_on_error(self):
        engine = self._make_engine()
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            reply = engine.respond("tell me a joke")
        # Should still return a non-empty string from the rules backend
        assert isinstance(reply, str)
        assert len(reply) > 0
