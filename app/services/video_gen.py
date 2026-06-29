"""
Video generation service — multi-backend, hardware-aware.

Priority:
  1. FramePack (local, best quality) — if installed via pip install framepack
  2. CogVideoX via diffusers (local, needs ~8GB VRAM)
  3. AnimateDiff via diffusers (local, lighter, 4GB VRAM)
  4. Replicate API (cloud fallback, needs REPLICATE_API_TOKEN)
  5. Placeholder
"""

import asyncio
import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.utils import logger


@dataclass
class VideoResult:
    ok: bool
    video_b64: str = ""
    file_path: str = ""
    url: str = ""
    backend: str = ""
    prompt: str = ""
    duration_s: float = 0.0
    fps: int = 8
    frames: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "video_b64": self.video_b64,
            "file_path": self.file_path,
            "url": self.url,
            "backend": self.backend,
            "prompt": self.prompt,
            "duration_s": round(self.duration_s, 2),
            "fps": self.fps,
            "frames": self.frames,
            "error": self.error,
        }


def _get_output_dir() -> Path:
    d = Path("data/videos")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_available_vram() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            return round(free / 1e9, 1)
    except Exception:
        pass
    return 0.0


async def _try_framepack(
    prompt: str, num_frames: int, fps: int, width: int, height: int
) -> VideoResult | None:
    try:
        import framepack  # noqa
    except ImportError:
        return None

    t0 = time.time()
    try:
        out_dir = _get_output_dir()
        fname = f"video_{int(t0)}.mp4"
        out_path = out_dir / fname

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _run_framepack(
            prompt, num_frames, fps, width, height, out_path
        ))

        if not out_path.exists():
            return None

        with open(out_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        return VideoResult(
            ok=True,
            video_b64=b64,
            file_path=str(out_path),
            url=f"/api/video/file/{fname}",
            backend="framepack",
            prompt=prompt,
            duration_s=time.time() - t0,
            fps=fps,
            frames=num_frames,
        )
    except Exception as e:
        logger.warning(f"FramePack failed: {e}")
        return None


def _run_framepack(prompt, num_frames, fps, width, height, out_path):
    import framepack
    gen = framepack.VideoGenerator()
    gen.generate(
        prompt=prompt,
        num_frames=num_frames,
        fps=fps,
        width=width,
        height=height,
        output_path=str(out_path),
    )


async def _try_cogvideox(
    prompt: str, num_frames: int, fps: int, width: int, height: int
) -> VideoResult | None:
    vram = _get_available_vram()
    if vram < 7.5:
        return None  # CogVideoX needs ~8GB VRAM
    try:
        import torch
        from diffusers import CogVideoXPipeline
    except ImportError:
        return None

    t0 = time.time()
    try:
        out_dir = _get_output_dir()
        fname = f"video_{int(t0)}.mp4"
        out_path = out_dir / fname

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _run_cogvideox(
            prompt, num_frames, fps, width, height, out_path
        ))

        if not out_path.exists():
            return None

        with open(out_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        return VideoResult(
            ok=True,
            video_b64=b64,
            file_path=str(out_path),
            url=f"/api/video/file/{fname}",
            backend="cogvideox",
            prompt=prompt,
            duration_s=time.time() - t0,
            fps=fps,
            frames=num_frames,
        )
    except Exception as e:
        logger.warning(f"CogVideoX failed: {e}")
        return None


def _run_cogvideox(prompt, num_frames, fps, width, height, out_path):
    import torch
    from diffusers import CogVideoXPipeline
    from diffusers.utils import export_to_video

    pipe = CogVideoXPipeline.from_pretrained(
        "THUDM/CogVideoX-2b",
        torch_dtype=torch.float16,
    ).to("cuda")
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_slicing()

    frames = pipe(
        prompt=prompt,
        num_frames=num_frames,
        guidance_scale=6.0,
    ).frames[0]

    export_to_video(frames, str(out_path), fps=fps)


async def _try_animatediff(
    prompt: str, num_frames: int, fps: int, width: int, height: int
) -> VideoResult | None:
    try:
        import torch
        from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler
    except ImportError:
        return None

    vram = _get_available_vram()
    if vram < 3.5:
        return None  # AnimateDiff needs ~4GB

    t0 = time.time()
    try:
        out_dir = _get_output_dir()
        fname = f"video_{int(t0)}.gif"
        out_path = out_dir / fname

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _run_animatediff(
            prompt, num_frames, fps, width, height, out_path
        ))

        if not out_path.exists():
            return None

        with open(out_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        return VideoResult(
            ok=True,
            video_b64=b64,
            file_path=str(out_path),
            url=f"/api/video/file/{fname}",
            backend="animatediff",
            prompt=prompt,
            duration_s=time.time() - t0,
            fps=fps,
            frames=num_frames,
        )
    except Exception as e:
        logger.warning(f"AnimateDiff failed: {e}")
        return None


def _run_animatediff(prompt, num_frames, fps, width, height, out_path):
    import torch
    from diffusers import AnimateDiffPipeline, MotionAdapter, DDIMScheduler
    from diffusers.utils import export_to_gif

    adapter = MotionAdapter.from_pretrained(
        "guoyww/animatediff-motion-adapter-v1-5-2",
        torch_dtype=torch.float16,
    )
    pipe = AnimateDiffPipeline.from_pretrained(
        "emilianJR/epiCRealism",
        motion_adapter=adapter,
        torch_dtype=torch.float16,
    ).to("cuda")
    pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config, beta_schedule="linear")

    output = pipe(prompt=prompt, num_frames=num_frames, guidance_scale=7.5)
    export_to_gif(output.frames[0], str(out_path))


async def _try_replicate(
    prompt: str, num_frames: int, fps: int, width: int, height: int
) -> VideoResult | None:
    token = os.getenv("REPLICATE_API_TOKEN", "")
    if not token:
        return None

    t0 = time.time()
    try:
        import httpx
        headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
        payload = {
            "version": "9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351",
            "input": {
                "prompt": prompt,
                "num_frames": num_frames,
                "fps": fps,
                "width": width,
                "height": height,
            },
        }
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.replicate.com/v1/predictions",
                json=payload,
                headers=headers,
            )
            if resp.status_code != 201:
                return None
            pred = resp.json()
            pred_id = pred["id"]

            # Poll until done
            for _ in range(120):
                await asyncio.sleep(3)
                poll = await client.get(
                    f"https://api.replicate.com/v1/predictions/{pred_id}",
                    headers=headers,
                )
                data = poll.json()
                if data["status"] == "succeeded":
                    video_url = data["output"]
                    if isinstance(video_url, list):
                        video_url = video_url[0]

                    vid_resp = await client.get(video_url)
                    b64 = base64.b64encode(vid_resp.content).decode()

                    out_dir = _get_output_dir()
                    fname = f"video_{int(t0)}.mp4"
                    out_path = out_dir / fname
                    out_path.write_bytes(vid_resp.content)

                    return VideoResult(
                        ok=True,
                        video_b64=b64,
                        file_path=str(out_path),
                        url=f"/api/video/file/{fname}",
                        backend="replicate",
                        prompt=prompt,
                        duration_s=time.time() - t0,
                        fps=fps,
                        frames=num_frames,
                    )
                elif data["status"] == "failed":
                    return None
    except Exception as e:
        logger.warning(f"Replicate video failed: {e}")
    return None


async def generate_video(
    prompt: str,
    num_frames: int = 16,
    fps: int = 8,
    width: int = 512,
    height: int = 320,
    backend: str = "auto",
) -> VideoResult:
    prompt = prompt.strip()
    if not prompt:
        return VideoResult(ok=False, error="Empty prompt")

    backends = [backend] if backend != "auto" else ["framepack", "cogvideox", "animatediff", "replicate"]

    for b in backends:
        result = None
        if b == "framepack":
            result = await _try_framepack(prompt, num_frames, fps, width, height)
        elif b == "cogvideox":
            result = await _try_cogvideox(prompt, num_frames, fps, width, height)
        elif b == "animatediff":
            result = await _try_animatediff(prompt, num_frames, fps, width, height)
        elif b == "replicate":
            result = await _try_replicate(prompt, num_frames, fps, width, height)

        if result and result.ok:
            logger.info(f"Video gen: {b} succeeded in {result.duration_s:.1f}s")
            return result

    return VideoResult(
        ok=False,
        error=(
            "No video backend available. Install one:\n"
            "• pip install framepack\n"
            "• pip install diffusers transformers accelerate torch (needs 4GB+ VRAM)\n"
            "• Set REPLICATE_API_TOKEN in .env for cloud generation"
        ),
    )


def list_saved_videos(limit: int = 20) -> list[dict]:
    out_dir = _get_output_dir()
    files = sorted(out_dir.glob("video_*"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    return [
        {
            "name": f.name,
            "url": f"/api/video/file/{f.name}",
            "size_mb": round(f.stat().st_size / 1e6, 2),
        }
        for f in files
    ]
