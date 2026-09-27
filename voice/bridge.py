"""Blast Radius — Voice Layer: Bhashini STT/TTS Bridge.

Implements four use cases from the project spec:
  1. speak_verdict()   — speak the risk-ranking verdict aloud after merge.py runs
  2. voice_confirm()   — listen for "confirm" or "abort" to gate fix-verify patching
  3. speak_status()    — periodic spoken progress update during long multi-subagent runs
  4. speak_intent_check() — "still reviewing the axios bump, correct?" intent check

Architecture:
  mic input → sounddevice → WAV bytes → Bhashini STT REST → text
  text       → Bhashini TTS REST → audio bytes → sounddevice playback

All credentials come from .env (BHASHINI_API_KEY, BHASHINI_STT_ENDPOINT, BHASHINI_TTS_ENDPOINT).
The bridge is fully testable with mock callbacks so the real Bhashini API is never
required during unit tests.
"""

from __future__ import annotations

import io
import os
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("[VOICE] sounddevice/numpy not installed — mic/speaker disabled. Running in text-only mode.")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration (loaded from .env, never hardcoded)
# ---------------------------------------------------------------------------

BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY", "")
BHASHINI_STT_ENDPOINT = os.getenv("BHASHINI_STT_ENDPOINT", "")
BHASHINI_TTS_ENDPOINT = os.getenv("BHASHINI_TTS_ENDPOINT", "")

SAMPLE_RATE = 16000   # Hz — Bhashini STT expects 16 kHz
CHANNELS = 1          # Mono
DTYPE = "int16"       # 16-bit PCM

CONFIRM_KEYWORDS = {"confirm", "yes", "proceed", "apply", "ok"}
ABORT_KEYWORDS = {"abort", "no", "cancel", "stop", "reject"}


# ---------------------------------------------------------------------------
# Audio capture helpers
# ---------------------------------------------------------------------------

def _write_wav_bytes(raw_pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """Wrap raw PCM bytes in a minimal RIFF/WAV container."""
    num_samples = len(raw_pcm) // 2  # int16 = 2 bytes each
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(raw_pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,               # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + raw_pcm


def capture_audio(duration_seconds: float = 4.0) -> Optional[bytes]:
    """Capture microphone audio and return raw WAV bytes.

    Returns None if audio hardware is unavailable.
    """
    if not AUDIO_AVAILABLE:
        print("[VOICE STT] Audio not available — no microphone capture.")
        return None

    print(f"[VOICE STT] Recording for {duration_seconds}s... (speak now)")
    try:
        recording = sd.rec(
            int(duration_seconds * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
        )
        sd.wait()
        raw_pcm = recording.tobytes()
        return _write_wav_bytes(raw_pcm)
    except Exception as err:
        print(f"[VOICE STT] Microphone capture failed: {err}")
        return None


def play_audio_bytes(audio_bytes: bytes) -> None:
    """Play raw audio bytes (WAV or MP3-like) through the system speaker.

    Falls back to writing a temp file and calling system player if sounddevice
    cannot handle the format directly.
    """
    if not AUDIO_AVAILABLE:
        print("[VOICE TTS] Audio not available — skipping playback.")
        return

    try:
        # Try sounddevice direct playback for WAV PCM
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        # Use sounddevice with the temp WAV file via numpy
        import wave
        with wave.open(tmp_path, "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            frames = wf.readframes(wf.getnframes())
            audio_array = np.frombuffer(frames, dtype=np.int16)
            if n_channels > 1:
                audio_array = audio_array.reshape(-1, n_channels)

        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()
    except Exception as err:
        print(f"[VOICE TTS] Playback error: {err}")
        # Fallback: write to disk so user can play manually
        output_path = Path("evidence/tts_output.wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)
        print(f"[VOICE TTS] Audio saved to {output_path} — play manually.")
    finally:
        try:
            if "tmp_path" in dir() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Bhashini API calls
# ---------------------------------------------------------------------------

def call_bhashini_stt(wav_bytes: bytes, language: str = "en") -> Optional[str]:
    """Send audio WAV bytes to Bhashini STT and return transcribed text.

    Returns None if the API call fails or credentials are absent.
    Never hardcodes credentials.
    """
    if not REQUESTS_AVAILABLE:
        print("[VOICE STT] requests not available.")
        return None

    api_key = BHASHINI_API_KEY
    endpoint = BHASHINI_STT_ENDPOINT

    if not api_key or not endpoint:
        print("[VOICE STT] BHASHINI_API_KEY or BHASHINI_STT_ENDPOINT not configured in .env.")
        return None

    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": api_key, "Content-Type": "audio/wav"},
            params={"language": language},
            data=wav_bytes,
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            transcript = data.get("transcript") or data.get("text") or ""
            return transcript.strip()
        else:
            print(f"[VOICE STT] API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as err:
        print(f"[VOICE STT] Request failed: {err}")
        return None


def call_bhashini_tts(text: str, language: str = "en", gender: str = "female") -> Optional[bytes]:
    """Send text to Bhashini TTS and return audio bytes (WAV).

    Returns None if credentials are absent or the call fails.
    Never hardcodes credentials.
    """
    if not REQUESTS_AVAILABLE:
        print("[VOICE TTS] requests not available.")
        return None

    api_key = BHASHINI_API_KEY
    endpoint = BHASHINI_TTS_ENDPOINT

    if not api_key or not endpoint:
        print("[VOICE TTS] BHASHINI_API_KEY or BHASHINI_TTS_ENDPOINT not configured in .env.")
        return None

    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={"text": text, "language": language, "gender": gender},
            timeout=15,
        )
        if response.status_code == 200:
            return response.content
        else:
            print(f"[VOICE TTS] API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as err:
        print(f"[VOICE TTS] Request failed: {err}")
        return None


# ---------------------------------------------------------------------------
# Core use cases
# ---------------------------------------------------------------------------

def speak_verdict(
    verdict_text: str,
    language: str = "en",
    tts_override: Optional[Callable[[str], Optional[bytes]]] = None,
) -> bool:
    """Use Case 1: Speak the risk-ranking verdict aloud.

    Args:
        verdict_text: The summary text to speak (from risk-rank verdict.summary)
        language: BCP-47 language code (default: 'en')
        tts_override: Injectable TTS callable for testing (avoids real API calls)

    Returns:
        True if audio was produced and played, False otherwise.
    """
    print(f"\n[VERDICT] Speaking verdict aloud ({language}):")
    print(f"  \"{verdict_text}\"")

    tts_fn = tts_override or (lambda t: call_bhashini_tts(t, language=language))
    audio = tts_fn(verdict_text)

    if not audio:
        print("[VERDICT] TTS produced no audio — falling back to text-only display.")
        return False

    play_audio_bytes(audio)
    return True


def voice_confirm(
    prompt_text: str = "Confirm patch application? Say 'confirm' or 'abort'.",
    language: str = "en",
    duration_seconds: float = 4.0,
    stt_override: Optional[Callable[[bytes], Optional[str]]] = None,
    tts_override: Optional[Callable[[str], Optional[bytes]]] = None,
    fallback_to_cli: bool = True,
) -> bool:
    """Use Case 2: Voice confirmation gate for fix-verify patch application.

    Speaks the prompt, captures the developer's spoken response,
    transcribes it, and returns True only if a confirm keyword is detected.
    Falls back to CLI input if audio is unavailable.

    Returns:
        True if confirmed, False if aborted or unclear.
    """
    print(f"\n[VOICE CONFIRM] Prompt: {prompt_text}")

    tts_fn = tts_override or (lambda t: call_bhashini_tts(t, language=language))
    audio_prompt = tts_fn(prompt_text)
    if audio_prompt:
        play_audio_bytes(audio_prompt)

    # Capture and transcribe
    wav_bytes = capture_audio(duration_seconds)
    if wav_bytes:
        stt_fn = stt_override or (lambda b: call_bhashini_stt(b, language=language))
        transcript = stt_fn(wav_bytes)
        if transcript:
            print(f"[VOICE CONFIRM] Transcribed: '{transcript}'")
            words = set(transcript.lower().split())
            if words & CONFIRM_KEYWORDS:
                print("[VOICE CONFIRM] Confirmed via voice.")
                return True
            elif words & ABORT_KEYWORDS:
                print("[VOICE CONFIRM] Aborted via voice.")
                return False
            else:
                print(f"[VOICE CONFIRM] Ambiguous transcript '{transcript}' — falling back to CLI.")

    if fallback_to_cli:
        print("[VOICE CONFIRM] Falling back to CLI prompt.")
        try:
            choice = input("Confirm patch? [y/N]: ").strip().lower()
            return choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    return False


def speak_status(
    message: str,
    language: str = "en",
    tts_override: Optional[Callable[[str], Optional[bytes]]] = None,
) -> None:
    """Use Case 3: Periodic spoken status update during long multi-subagent runs."""
    print(f"\n[STATUS] {message}")
    tts_fn = tts_override or (lambda t: call_bhashini_tts(t, language=language))
    audio = tts_fn(message)
    if audio:
        play_audio_bytes(audio)


def speak_intent_check(
    package_name: str = "axios",
    old_version: str = "1.4.0",
    new_version: str = "1.7.2",
    language: str = "en",
    tts_override: Optional[Callable[[str], Optional[bytes]]] = None,
) -> None:
    """Use Case 4: Intent check if a run drifts long.

    Speaks: "Still reviewing the <package> <old> to <new> bump, correct?"
    """
    intent_msg = (
        f"Still reviewing the {package_name} {old_version} to {new_version} bump, correct? "
        "Please respond to confirm you are still present."
    )
    speak_status(intent_msg, language=language, tts_override=tts_override)


# ---------------------------------------------------------------------------
# Bob Shell subprocess integration (Phase 10 wiring point)
# ---------------------------------------------------------------------------

def invoke_bob_shell(command: str, bob_shell_path: Optional[str] = None) -> str:
    """Pipe a command into Bob Shell non-interactively and return its text output.

    This is the subprocess integration point. In Phase 10, bob_shell_path
    is set to the real Bob Shell binary. Until then, it's a placeholder that
    returns a simulated response.

    Never calls any real Bhashini or Bob API without credentials configured.
    """
    bob_shell_path = bob_shell_path or os.getenv("BOB_SHELL_PATH", "")

    if not bob_shell_path:
        print("[BOB SHELL] BOB_SHELL_PATH not configured — returning mock response.")
        return f"[MOCK] Bob Shell response to: '{command}'"

    try:
        proc = subprocess.run(
            [bob_shell_path, "--mode", "blast-radius", "--non-interactive"],
            input=command,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.stdout.strip() or proc.stderr.strip()
    except FileNotFoundError:
        return "[ERROR] Bob Shell binary not found."
    except subprocess.TimeoutExpired:
        return "[ERROR] Bob Shell timed out."
    except Exception as err:
        return f"[ERROR] Bob Shell invocation failed: {err}"


# ---------------------------------------------------------------------------
# Convenience: full voice pipeline round-trip
# ---------------------------------------------------------------------------

def run_voice_pipeline(
    verdict_summary: str,
    package_name: str = "axios",
    old_version: str = "1.4.0",
    new_version: str = "1.7.2",
    language: str = "en",
    tts_override: Optional[Callable[[str], Optional[bytes]]] = None,
    stt_override: Optional[Callable[[bytes], Optional[str]]] = None,
) -> bool:
    """Run the complete voice pipeline for a single Blast Radius verdict.

    1. Speak the verdict aloud.
    2. Ask for voice confirmation.
    3. Return True if confirmed, False if aborted.
    """
    speak_verdict(verdict_summary, language=language, tts_override=tts_override)
    time.sleep(0.5)

    confirmed = voice_confirm(
        prompt_text="Do you want to apply the proposed patch? Say confirm or abort.",
        language=language,
        tts_override=tts_override,
        stt_override=stt_override,
    )
    return confirmed


# ---------------------------------------------------------------------------
# CLI entrypoint for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Blast Radius Voice Bridge — Standalone Test")
    parser.add_argument("--mode", choices=["verdict", "confirm", "status", "intent", "roundtrip"],
                        default="verdict", help="Which use case to test")
    parser.add_argument("--text", type=str, default="", help="Text to synthesize (for verdict/status)")
    parser.add_argument("--language", type=str, default="en", help="BCP-47 language code")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual Bhashini API calls")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Bhashini API calls suppressed. Printing text only.")
        mock_tts = lambda t: None  # noqa: E731
        mock_stt = lambda b: "confirm"  # noqa: E731
    else:
        mock_tts = None
        mock_stt = None

    if args.mode == "verdict":
        text = args.text or "Risk tier: merge with patch. Confidence: 87 percent."
        speak_verdict(text, language=args.language, tts_override=mock_tts)

    elif args.mode == "confirm":
        result = voice_confirm(language=args.language, tts_override=mock_tts, stt_override=mock_stt)
        print(f"Confirmation result: {result}")

    elif args.mode == "status":
        text = args.text or "Running vulnerability lookup. Please wait."
        speak_status(text, language=args.language, tts_override=mock_tts)

    elif args.mode == "intent":
        speak_intent_check(language=args.language, tts_override=mock_tts)

    elif args.mode == "roundtrip":
        verdict_text = args.text or ("Bumping axios from 1.4.0 to 1.7.2 closes CVE-2023-45857. "
                                     "One breaking change has a mechanical fix available. Risk tier: merge with patch.")
        confirmed = run_voice_pipeline(
            verdict_text,
            language=args.language,
            tts_override=mock_tts,
            stt_override=mock_stt,
        )
        print(f"Pipeline result: {'CONFIRMED' if confirmed else 'ABORTED'}")
