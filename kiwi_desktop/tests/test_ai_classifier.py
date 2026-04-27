"""Tests for Ollama classifier helpers."""

from __future__ import annotations

import urllib.error

from services.ai_classifier import OllamaAIClassifier


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb


def test_ollama_test_connection_success(monkeypatch) -> None:
    def _fake_urlopen(_req, timeout):
        del timeout
        return _FakeResponse('{"modelfile":"llama3.2:3b"}')

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    checker = OllamaAIClassifier(model="llama3.2:3b", timeout_s=1.0)
    ok, message = checker.test_connection()
    assert ok is True
    assert "reachable" in message.lower()


def test_ollama_test_connection_failure(monkeypatch) -> None:
    def _fake_urlopen(_req, timeout):
        del timeout
        raise urllib.error.URLError("refused")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    checker = OllamaAIClassifier(model="llama3.2:3b", timeout_s=1.0)
    ok, message = checker.test_connection()
    assert ok is False
    assert "failed" in message.lower()


def test_ollama_list_models_success(monkeypatch) -> None:
    def _fake_urlopen(_req, timeout):
        del timeout
        return _FakeResponse('{"models":[{"name":"llama3.2:3b"},{"name":"mistral:7b"}]}')

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    checker = OllamaAIClassifier(model="llama3.2:3b", timeout_s=1.0)
    ok, models, message = checker.list_models()
    assert ok is True
    assert models == ("llama3.2:3b", "mistral:7b")
    assert "loaded" in message.lower()


def test_ollama_list_models_failure(monkeypatch) -> None:
    def _fake_urlopen(_req, timeout):
        del timeout
        raise urllib.error.URLError("refused")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    checker = OllamaAIClassifier(model="llama3.2:3b", timeout_s=1.0)
    ok, models, message = checker.list_models()
    assert ok is False
    assert models == ()
    assert "failed" in message.lower()
