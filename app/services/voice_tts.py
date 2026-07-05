"""
Voice TTS — text to speech.

Priority:
  1. Piper (local, offline, fast) — if piper binary on PATH
  2. Windows SAPI (local, offline, built-in on Windows) — via PowerShell
  3. gTTS  (Google TTS, cloud, free, requires internet)

Returns path to a .mp3 / .wav file in /tmp. Caller is responsible for cleanup.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from app.utils import logger


async def speak(text: str, lang: str = "en") -> str:
    """
    Convert text to speech. Returns path to audio file.
    Raises RuntimeError if both backends fail.
    """
    text = text.strip()[:2000]  # cap for sanity

    # Try Piper first (local, offline)
    try:
        path = await _piper_tts(text)
        if path:
            return path
    except Exception as e:
        logger.debug(f"Piper TTS failed: {e}")

    # Windows built-in SAPI (offline, no deps)
    try:
        path = await _sapi_tts(text)
        if path:
            return path
    except Exception as e:
        logger.debug(f"SAPI TTS failed: {e}")

    # Fallback: gTTS
    try:
        path = await _gtts(text, lang)
        if path:
            return path
    except Exception as e:
        logger.debug(f"gTTS failed: {e}")

    raise RuntimeError("All TTS backends failed. Install gtts: pip install gtts")


async def _piper_tts(text: str) -> str | None:
    """Run piper CLI if available. Returns path to .wav or None."""
    import shutil
    if not shutil.which("piper"):
        return None

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        proc = await asyncio.create_subprocess_exec(
            "piper", "--output_file", path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate(input=text.encode())
        if proc.returncode == 0 and Path(path).stat().st_size > 0:
            logger.info("TTS: used Piper (local)")
            return path
    except Exception as e:
        logger.debug(f"Piper exec error: {e}")
    try:
        os.unlink(path)
    except Exception:
        pass
    return None


async def _sapi_tts(text: str) -> str | None:
    """Windows built-in System.Speech TTS via PowerShell. Offline, zero deps."""
    if os.name != "nt":
        return None

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    # Text passed via stdin to avoid any quoting/injection issues
    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{path}'); "
        "$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(input=text.encode("utf-8")), timeout=60)
        if proc.returncode == 0 and Path(path).stat().st_size > 44:  # >WAV header
            logger.info("TTS: used Windows SAPI (local)")
            return path
    except Exception as e:
        logger.debug(f"SAPI exec error: {e}")
    try:
        os.unlink(path)
    except Exception:
        pass
    return None


async def _gtts(text: str, lang: str = "en") -> str:
    """gTTS cloud TTS. Returns .mp3 path."""
    from gtts import gTTS  # type: ignore
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    loop = asyncio.get_event_loop()

    def _run():
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(path)

    await loop.run_in_executor(None, _run)
    logger.info("TTS: used gTTS (cloud)")
    return path
