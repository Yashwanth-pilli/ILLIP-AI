"""
Image generation service — hardware-aware, multi-backend.

Priority order:
  1. Local diffusers (GPU/CPU) — fully offline
  2. Automatic1111 API (if running locally)
  3. Together AI API (cloud fallback, needs TOGETHER_API_KEY)
  4. Placeholder (no backend available)
"""

import asyncio
import base64
import io
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.utils import logger


@dataclass
class ImageResult:
    ok: bool
    image_b64: str = ""
    file_path: str = ""
    url: str = ""
    backend: str = ""
    prompt: str = ""
    width: int = 512
    height: int = 512
    duration_s: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "image_b64": self.image_b64,
            "file_path": self.file_path,
            "url": self.url,
            "backend": self.backend,
            "prompt": self.prompt,
            "width": self.width,
            "height": self.height,
            "duration_s": round(self.duration_s, 2),
            "error": self.error,
        }


def _get_output_dir() -> Path:
    d = Path("data/images")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _detect_best_model() -> str:
    """Pick SD model based on available VRAM."""
    try:
        import torch
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            if vram_gb >= 10:
                return "stabilityai/stable-diffusion-xl-base-1.0"
            elif vram_gb >= 6:
                return "runwayml/stable-diffusion-v1-5"
            else:
                return "OFA-Sys/small-stable-diffusion-v0"
    except Exception:
        pass
    return "runwayml/stable-diffusion-v1-5"


async def _generate_local_diffusers(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    model_id: str,
) -> ImageResult:
    """Local generation via diffusers — runs in thread pool to avoid blocking."""
    t0 = time.time()

    def _run():
        import torch
        from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline, AutoPipelineForText2Image

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info(f"Loading {model_id} on {device}...")
        pipe = AutoPipelineForText2Image.from_pretrained(
            model_id,
            torch_dtype=dtype,
            use_safetensors=True,
            variant="fp16" if device == "cuda" else None,
        )
        pipe = pipe.to(device)

        if device == "cpu":
            pipe.enable_attention_slicing()

        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or "blurry, low quality, ugly, deformed",
            width=width,
            height=height,
            num_inference_steps=steps,
        )
        return result.images[0]

    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, _run)

        # Save to file
        out_path = _get_output_dir() / f"img_{int(time.time())}.png"
        image.save(str(out_path))

        # Also return as base64
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        return ImageResult(
            ok=True,
            image_b64=b64,
            file_path=str(out_path),
            url=f"/data/images/{out_path.name}",
            backend="diffusers",
            prompt=prompt,
            width=width,
            height=height,
            duration_s=time.time() - t0,
        )
    except Exception as e:
        return ImageResult(ok=False, error=f"diffusers: {e}", backend="diffusers")


async def _generate_a1111(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
) -> ImageResult:
    """Automatic1111 WebUI API (http://localhost:7860)."""
    import httpx
    t0 = time.time()
    base = os.getenv("A1111_URL", "http://localhost:7860")
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{base}/sdapi/v1/txt2img", json={
                "prompt": prompt,
                "negative_prompt": negative_prompt or "",
                "width": width,
                "height": height,
                "steps": steps,
                "cfg_scale": 7,
                "sampler_name": "DPM++ 2M Karras",
            })
            r.raise_for_status()
            data = r.json()

        b64 = data["images"][0]
        img_bytes = base64.b64decode(b64)
        out_path = _get_output_dir() / f"img_{int(time.time())}.png"
        out_path.write_bytes(img_bytes)

        return ImageResult(
            ok=True,
            image_b64=b64,
            file_path=str(out_path),
            url=f"/data/images/{out_path.name}",
            backend="automatic1111",
            prompt=prompt,
            width=width,
            height=height,
            duration_s=time.time() - t0,
        )
    except Exception as e:
        return ImageResult(ok=False, error=f"a1111: {e}", backend="automatic1111")


async def _generate_together(
    prompt: str,
    width: int,
    height: int,
) -> ImageResult:
    """Together AI image API — cloud fallback."""
    import httpx
    t0 = time.time()
    key = os.getenv("TOGETHER_API_KEY", "")
    if not key:
        return ImageResult(ok=False, error="TOGETHER_API_KEY not set", backend="together")

    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.together.xyz/v1/images/generations",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "black-forest-labs/FLUX.1-schnell-Free",
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "steps": 4,
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            r.raise_for_status()
            b64 = r.json()["data"][0]["b64_json"]

        img_bytes = base64.b64decode(b64)
        out_path = _get_output_dir() / f"img_{int(time.time())}.png"
        out_path.write_bytes(img_bytes)

        return ImageResult(
            ok=True,
            image_b64=b64,
            file_path=str(out_path),
            url=f"/data/images/{out_path.name}",
            backend="together_ai",
            prompt=prompt,
            width=width,
            height=height,
            duration_s=time.time() - t0,
        )
    except Exception as e:
        return ImageResult(ok=False, error=f"together: {e}", backend="together")


async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    backend: str = "auto",
    model_id: str = "",
) -> ImageResult:
    """
    Main entry. Auto-selects best available backend.
    backend: "auto" | "diffusers" | "a1111" | "together"
    """
    if backend == "a1111" or backend == "auto":
        # Check if A1111 is running
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                await c.get(os.getenv("A1111_URL", "http://localhost:7860") + "/sdapi/v1/samplers")
            result = await _generate_a1111(prompt, negative_prompt, width, height, steps)
            if result.ok:
                return result
        except Exception:
            pass

    if backend == "diffusers" or backend == "auto":
        try:
            import diffusers  # noqa
            mid = model_id or _detect_best_model()
            result = await _generate_local_diffusers(prompt, negative_prompt, width, height, steps, mid)
            if result.ok:
                return result
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"diffusers failed: {e}")

    if backend == "together" or backend == "auto":
        result = await _generate_together(prompt, width, height)
        if result.ok:
            return result

    return ImageResult(
        ok=False,
        error=(
            "No image backend available. Options:\n"
            "1. pip install diffusers transformers accelerate torch\n"
            "2. Run Automatic1111 at localhost:7860\n"
            "3. Set TOGETHER_API_KEY in .env (free tier available)"
        ),
        backend="none",
    )


def list_saved_images(limit: int = 20) -> list[dict]:
    d = _get_output_dir()
    files = sorted(d.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [
        {"name": f.name, "url": f"/data/images/{f.name}", "size_kb": f.stat().st_size // 1024}
        for f in files[:limit]
    ]
