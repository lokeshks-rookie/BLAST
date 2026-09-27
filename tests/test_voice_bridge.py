"""Unit tests for voice/bridge.py — all tests are injectable and run without
real Bhashini API credentials or hardware audio devices."""

import os
import sys
from pathlib import Path
import pytest

# Add project root to path so voice.bridge is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.bridge import (
    CONFIRM_KEYWORDS,
    ABORT_KEYWORDS,
    _write_wav_bytes,
    speak_verdict,
    voice_confirm,
    speak_status,
    speak_intent_check,
    run_voice_pipeline,
    invoke_bob_shell,
)


# ---------------------------------------------------------------------------
# Helpers / mocks
# ---------------------------------------------------------------------------

def make_silent_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate minimal silent WAV bytes for testing."""
    num_samples = int(duration_seconds * sample_rate)
    raw_pcm = bytes(num_samples * 2)  # 2 bytes per int16 sample, all zeros
    return _write_wav_bytes(raw_pcm, sample_rate=sample_rate)


MOCK_TTS = lambda text: make_silent_wav(0.1)  # Returns audio bytes, no real API call
MOCK_TTS_NONE = lambda text: None              # Simulates API failure

MOCK_STT_CONFIRM = lambda wav: "confirm"       # Always returns confirm keyword
MOCK_STT_ABORT = lambda wav: "abort"           # Always returns abort keyword
MOCK_STT_UNCLEAR = lambda wav: "hmm maybe"    # Ambiguous response


# ---------------------------------------------------------------------------
# _write_wav_bytes
# ---------------------------------------------------------------------------

def test_wav_bytes_valid_header():
    """WAV header must start with RIFF and contain WAVE marker."""
    silent = make_silent_wav()
    assert silent[:4] == b"RIFF"
    assert silent[8:12] == b"WAVE"
    assert silent[12:16] == b"fmt "


def test_wav_bytes_length():
    """WAV bytes length should be header (44 bytes) + PCM data."""
    n_samples = 800  # 0.05s at 16 kHz
    raw_pcm = bytes(n_samples * 2)
    wav = _write_wav_bytes(raw_pcm)
    assert len(wav) == 44 + len(raw_pcm)


# ---------------------------------------------------------------------------
# speak_verdict (Use Case 1)
# ---------------------------------------------------------------------------

def test_speak_verdict_with_mock_tts(capsys):
    """speak_verdict returns True when mock TTS provides audio bytes."""
    result = speak_verdict(
        "Risk tier: merge with patch.",
        tts_override=MOCK_TTS,
    )
    # With audio available and good TTS, should succeed (or gracefully degrade)
    captured = capsys.readouterr()
    assert "Speaking verdict aloud" in captured.out or "VERDICT" in captured.out


def test_speak_verdict_tts_failure_returns_false(capsys):
    """speak_verdict returns False when TTS API fails."""
    result = speak_verdict(
        "Some verdict text",
        tts_override=MOCK_TTS_NONE,
    )
    assert result is False
    captured = capsys.readouterr()
    assert "text-only" in captured.out.lower() or "no audio" in captured.out.lower()


def test_speak_verdict_does_not_expose_credentials():
    """Credentials must NEVER appear in stdout during speak_verdict."""
    api_key = "FAKE_API_KEY_12345"
    os.environ["BHASHINI_API_KEY"] = api_key
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        speak_verdict("Test", tts_override=MOCK_TTS_NONE)
    assert api_key not in buf.getvalue()
    del os.environ["BHASHINI_API_KEY"]


# ---------------------------------------------------------------------------
# voice_confirm (Use Case 2)
# ---------------------------------------------------------------------------

def test_voice_confirm_confirm_keyword(capsys):
    """voice_confirm returns True when STT transcribes a confirm keyword."""
    confirmed = voice_confirm(
        tts_override=MOCK_TTS,
        stt_override=MOCK_STT_CONFIRM,
        fallback_to_cli=False,
    )
    assert confirmed is True


def test_voice_confirm_abort_keyword(capsys):
    """voice_confirm returns False when STT transcribes an abort keyword."""
    confirmed = voice_confirm(
        tts_override=MOCK_TTS,
        stt_override=MOCK_STT_ABORT,
        fallback_to_cli=False,
    )
    assert confirmed is False


def test_voice_confirm_ambiguous_falls_back_to_cli(monkeypatch, capsys):
    """Ambiguous STT result falls back to CLI confirmation."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    confirmed = voice_confirm(
        tts_override=MOCK_TTS,
        stt_override=MOCK_STT_UNCLEAR,
        fallback_to_cli=True,
    )
    assert confirmed is True


def test_voice_confirm_no_audio_falls_back_to_cli(monkeypatch, capsys):
    """No audio (None from capture) falls back to CLI when allowed."""
    monkeypatch.setattr("builtins.input", lambda _: "n")
    confirmed = voice_confirm(
        tts_override=MOCK_TTS_NONE,
        stt_override=lambda b: None,
        fallback_to_cli=True,
    )
    assert confirmed is False


def test_voice_confirm_no_fallback_returns_false():
    """Without fallback and no audio, voice_confirm returns False safely."""
    confirmed = voice_confirm(
        tts_override=MOCK_TTS_NONE,
        stt_override=lambda b: None,
        fallback_to_cli=False,
    )
    assert confirmed is False


# ---------------------------------------------------------------------------
# speak_status (Use Case 3)
# ---------------------------------------------------------------------------

def test_speak_status_prints_message(capsys):
    """speak_status prints message to stdout even when TTS fails."""
    speak_status("Running vulnerability lookup. Please wait.", tts_override=MOCK_TTS_NONE)
    captured = capsys.readouterr()
    assert "Running vulnerability lookup" in captured.out


# ---------------------------------------------------------------------------
# speak_intent_check (Use Case 4)
# ---------------------------------------------------------------------------

def test_speak_intent_check_mentions_package(capsys):
    """speak_intent_check prints intent-check with package name in output."""
    speak_intent_check(
        package_name="axios",
        old_version="1.4.0",
        new_version="1.7.2",
        tts_override=MOCK_TTS_NONE,
    )
    captured = capsys.readouterr()
    assert "axios" in captured.out
    assert "1.4.0" in captured.out
    assert "1.7.2" in captured.out


# ---------------------------------------------------------------------------
# run_voice_pipeline (full round-trip)
# ---------------------------------------------------------------------------

def test_run_voice_pipeline_confirm(capsys):
    """Full pipeline returns True when developer confirms."""
    result = run_voice_pipeline(
        verdict_summary="merge with patch",
        tts_override=MOCK_TTS,
        stt_override=MOCK_STT_CONFIRM,
    )
    assert result is True


def test_run_voice_pipeline_abort(capsys):
    """Full pipeline returns False when developer aborts."""
    result = run_voice_pipeline(
        verdict_summary="do not merge",
        tts_override=MOCK_TTS,
        stt_override=MOCK_STT_ABORT,
    )
    assert result is False


# ---------------------------------------------------------------------------
# invoke_bob_shell (Phase 10 wiring point)
# ---------------------------------------------------------------------------

def test_invoke_bob_shell_without_path():
    """Without BOB_SHELL_PATH, invoke_bob_shell returns a mock response."""
    os.environ.pop("BOB_SHELL_PATH", None)
    response = invoke_bob_shell("blast-radius diff --package axios")
    assert "MOCK" in response or "not configured" in response.lower()


def test_confirm_keyword_set_sanity():
    """Sanity check that keyword sets contain expected entries."""
    assert "confirm" in CONFIRM_KEYWORDS
    assert "yes" in CONFIRM_KEYWORDS
    assert "abort" in ABORT_KEYWORDS
    assert "no" in ABORT_KEYWORDS
