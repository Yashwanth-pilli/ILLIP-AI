"""Video generation API."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.video_gen import generate_video, list_saved_videos
from app.utils import logger

router = APIRouter(prefix="/video", tags=["video"])

_VIDEO_DIR = Path("data/videos")


class VideoGenRequest(BaseModel):
    prompt: str
    num_frames: int = 16
    fps: int = 8
    width: int = 512
    height: int = 320
    backend: str = "auto"


@router.post("/generate")
async def gen_video(req: VideoGenRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")
    result = await generate_video(
        prompt=req.prompt,
        num_frames=req.num_frames,
        fps=req.fps,
        width=req.width,
        height=req.height,
        backend=req.backend,
    )
    return result.to_dict()


@router.get("/gallery")
async def get_gallery(limit: int = Query(20, le=100)):
    return {"videos": list_saved_videos(limit)}


@router.get("/file/{filename}")
async def get_video_file(filename: str):
    path = _VIDEO_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Video not found")
    # Prevent path traversal
    if not str(path.resolve()).startswith(str(_VIDEO_DIR.resolve())):
        raise HTTPException(403, "Forbidden")
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/gif"
    return FileResponse(str(path), media_type=media_type)


@router.get("/backends")
async def get_backends():
    backends = []

    # FramePack
    try:
        import framepack  # noqa
        backends.append({"id": "framepack", "name": "FramePack (local)", "available": True, "type": "local"})
    except ImportError:
        backends.append({"id": "framepack", "name": "FramePack", "available": False, "note": "pip install framepack"})

    # CogVideoX
    try:
        import torch
        from diffusers import CogVideoXPipeline  # noqa
        gpu = torch.cuda.is_available()
        vram = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if gpu else 0
        ok = gpu and vram >= 7.5
        backends.append({
            "id": "cogvideox",
            "name": "CogVideoX-2b (local)",
            "available": ok,
            "type": "local",
            "gpu": gpu,
            "vram_gb": vram,
            "note": "" if ok else f"Needs 8GB VRAM (have {vram}GB)",
        })
    except ImportError:
        backends.append({"id": "cogvideox", "name": "CogVideoX", "available": False,
                         "note": "pip install diffusers transformers accelerate torch"})

    # AnimateDiff
    try:
        import torch
        from diffusers import AnimateDiffPipeline  # noqa
        gpu = torch.cuda.is_available()
        vram = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if gpu else 0
        ok = gpu and vram >= 3.5
        backends.append({
            "id": "animatediff",
            "name": "AnimateDiff (local, GIF)",
            "available": ok,
            "type": "local",
            "note": "" if ok else f"Needs 4GB VRAM (have {vram}GB)",
        })
    except ImportError:
        backends.append({"id": "animatediff", "name": "AnimateDiff", "available": False,
                         "note": "pip install diffusers transformers accelerate torch"})

    # Replicate
    token = os.getenv("REPLICATE_API_TOKEN", "")
    backends.append({
        "id": "replicate",
        "name": "Replicate (cloud)",
        "available": bool(token),
        "type": "cloud",
        "note": "" if token else "Set REPLICATE_API_TOKEN in .env",
    })

    return {"backends": backends}
