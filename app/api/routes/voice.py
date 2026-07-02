"""
Voice endpoints — STT (Whisper) + TTS (Piper if installed, else frontend handles it).

POST /api/voice/transcribe  — audio file -> text
POST /api/voice/speak       — text -> audio bytes (WAV)
GET  /api/voice/status      — what's available
"""

import tempfile
import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from app.utils import logger
from app.config import settings

router = APIRouter(prefix="/voice", tags=["voice"])

# Whisper model — loaded once, reused. "base" = 74MB, fast, good accuracy.
# Configurable via WHISPER_MODEL env var.
_WHISPER_MODEL = None
_WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")


def _get_whisper():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        try:
            from faster_whisper import WhisperModel
            device = "cuda" if _has_cuda() else "cpu"
            compute = "float16" if device == "cuda" else "int8"
            logger.info(f"Loading Whisper {_WHISPER_MODEL_SIZE} on {device}/{compute}...")
            _WHISPER_MODEL = WhisperModel(_WHISPER_MODEL_SIZE, device=device, compute_type=compute)
            logger.info("Whisper ready")
        except ImportError:
            raise HTTPException(status_code=503, detail="faster-whisper not installed. Run: pip install faster-whisper")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Whisper load failed: {e}")
    return _WHISPER_MODEL


def _has_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_supported_compute_types("cuda") != []
    except Exception:
        return False


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio to text using local Whisper model.
    Accepts: WebM, OGG, WAV, MP3, M4A (anything ffmpeg can read).
    Returns: { text, language, duration_s }
    """
    model = _get_whisper()

    # Save upload to temp file (keep extension so ffmpeg knows format)
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            language=None,      # auto-detect language
            task="transcribe",
            vad_filter=True,    # skip silent parts
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "duration_s": round(info.duration, 1),
        }
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/speak")
async def speak_text(body: dict):
    """
    Convert text to speech using Piper TTS (if installed).
    Returns: audio/wav stream.
    If Piper not installed, returns 501 — frontend falls back to browser speechSynthesis.
    """
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    # Try Piper binary
    try:
        import subprocess, shutil
        piper_bin = shutil.which("piper")
        if not piper_bin:
            raise HTTPException(
                status_code=501,
                detail="Piper TTS not installed. Frontend will use browser speechSynthesis."
            )

        # Default voice model path — configurable via PIPER_VOICE env var
        voice_model = os.environ.get(
            "PIPER_VOICE",
            str(settings.get_data_path() / "voices" / "en_US-lessac-medium.onnx")
        )
        if not Path(voice_model).exists():
            raise HTTPException(
                status_code=503,
                detail=f"Voice model not found: {voice_model}. Download from https://huggingface.co/rhasspy/piper-voices"
            )

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
            out_path = out.name

        proc = subprocess.run(
            [piper_bin, "--model", voice_model, "--output_file", out_path],
            input=text.encode(),
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Piper error: {proc.stderr.decode()}")

        def iter_audio():
            with open(out_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
            try:
                os.unlink(out_path)
            except Exception:
                pass

        return StreamingResponse(iter_audio(), media_type="audio/wav")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vision/analyze")
async def vision_analyze(
    file: UploadFile = File(...),
    prompt: str = "Describe this image in detail.",
):
    """
    Analyze an image using the local vision model (LLaVA family).
    Returns a text description / answer to the prompt.
    POST multipart: file (image) + optional prompt form field.
    """
    from app.skills.builtin.vision_skill import analyze_image
    from app.config import settings as _cfg

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    result = await analyze_image(data, prompt, _cfg.ollama_base_url)
    return {"description": result, "prompt": prompt, "filename": file.filename}


@router.post("/document/analyze")
async def document_analyze(file: UploadFile = File(...)):
    """
    Extract text from an uploaded PDF (no image pipeline, no vision model).
    POST multipart: file (application/pdf). Returns extracted text for the
    frontend to fold into the next chat message as context.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported here")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    import tempfile as _tempfile
    tmp_path = None
    try:
        with _tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        from app.skills.builtin.pdf_reader import _extract_pdfplumber, _extract_pypdf
        max_pages = 20
        try:
            text = _extract_pdfplumber(tmp_path, max_pages)
        except ImportError:
            try:
                text = _extract_pypdf(tmp_path, max_pages)
            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="No PDF library installed. Run: pip install pdfplumber",
                )
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not text.strip():
        return {
            "text": "",
            "filename": file.filename,
            "error": "No text extracted — this PDF may be scanned (image-based). OCR not yet supported.",
        }

    char_limit = 8000
    truncated = len(text) > char_limit
    if truncated:
        text = text[:char_limit]

    return {"text": text, "filename": file.filename, "truncated": truncated}


@router.get("/status")
async def voice_status():
    """What voice/vision features are available."""
    stt_ok = _get_whisper() is not None
    try:
        import subprocess, shutil
        tts_ok = shutil.which("piper") is not None
    except Exception:
        tts_ok = False

    from app.skills.builtin.vision_skill import _detect_vision_model
    from app.config import settings as _cfg
    vision_model = await _detect_vision_model(_cfg.ollama_base_url)

    return {
        "stt": stt_ok,
        "stt_model": os.environ.get("WHISPER_MODEL", "base") if stt_ok else None,
        "tts_backend": "piper" if tts_ok else "browser",
        "tts_note": None if tts_ok else "Using browser speechSynthesis (no backend TTS installed)",
        "install_stt": None if stt_ok else "pip install faster-whisper",
        "install_tts": None if tts_ok else "https://github.com/rhasspy/piper/releases",
        "vision_model": vision_model,
        "vision_ready": vision_model is not None,
        "install_vision": None if vision_model else "ollama pull llava-phi3",
    }
