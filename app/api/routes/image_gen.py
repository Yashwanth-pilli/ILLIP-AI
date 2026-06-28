"""Image Generation API."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.image_gen import generate_image, list_saved_images
from app.utils import logger

router = APIRouter(prefix="/image", tags=["image"])


class ImageGenRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 20
    backend: str = "auto"
    model_id: str = ""


@router.post("/generate")
async def gen_image(req: ImageGenRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")

    result = await generate_image(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        width=req.width,
        height=req.height,
        steps=req.steps,
        backend=req.backend,
        model_id=req.model_id,
    )
    return result.to_dict()


@router.get("/gallery")
async def get_gallery(limit: int = Query(20, le=100)):
    return {"images": list_saved_images(limit)}


@router.get("/backends")
async def get_backends():
    """Return which backends are available."""
    backends = []

    # Check A1111
    import os
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            await c.get(os.getenv("A1111_URL", "http://localhost:7860") + "/sdapi/v1/samplers")
        backends.append({"id": "a1111", "name": "Automatic1111", "available": True, "type": "local"})
    except Exception:
        backends.append({"id": "a1111", "name": "Automatic1111", "available": False, "note": "Start A1111 at localhost:7860"})

    # Check diffusers
    try:
        import diffusers  # noqa
        import torch
        gpu = torch.cuda.is_available()
        vram = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if gpu else 0
        backends.append({
            "id": "diffusers",
            "name": "Stable Diffusion (local)",
            "available": True,
            "type": "local",
            "gpu": gpu,
            "vram_gb": vram,
        })
    except ImportError:
        backends.append({
            "id": "diffusers",
            "name": "Stable Diffusion (local)",
            "available": False,
            "note": "pip install diffusers transformers accelerate torch",
        })

    # Check Together AI
    together_key = os.getenv("TOGETHER_API_KEY", "")
    backends.append({
        "id": "together",
        "name": "FLUX (Together AI)",
        "available": bool(together_key),
        "type": "cloud",
        "note": "" if together_key else "Set TOGETHER_API_KEY in .env",
    })

    return {"backends": backends}
