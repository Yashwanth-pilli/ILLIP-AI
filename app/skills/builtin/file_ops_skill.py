"""
File ops skills — move/copy real files between folders and drives (C: -> E: etc).

This is the one place ILLIP is allowed to WRITE outside its workspace sandbox,
so the safety model is strict:

  * dry_run-by-default: confirm=False only REPORTS what would happen. The model
    must show the user the plan and get a yes before calling with confirm=True.
  * System locations are refused outright (Windows, Program Files, ProgramData,
    the ILLIP install itself) — as source OR destination.
  * Credential material (.env, ssh keys, cloud creds) is refused, same list the
    read-anywhere skill uses.
  * Never overwrites: if the destination exists the move/copy is refused unless
    overwrite=True is passed explicitly (a separate, deliberate step).
  * Moves are copy-then-verify-then-delete for files (never lose data to a
    half-finished cross-drive move); shutil.move for dirs (it does the same).
"""

import os
import shutil
from pathlib import Path

from app.skills.base_skill import BaseSKill
from app.utils import logger

# Locations we never read from or write to — breaking these breaks the PC.
# POSIX roots matter too: Docker deploys run this on Linux.
_POSIX_FORBIDDEN = ("/etc", "/usr", "/bin", "/sbin", "/lib", "/boot", "/var", "/root", "/proc", "/sys", "/dev")


def _forbidden_roots() -> list[Path]:
    roots = []
    for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(env)
        if v:
            roots.append(Path(v))
    if os.name != "nt":
        roots.extend(Path(p) for p in _POSIX_FORBIDDEN)
    # The ILLIP install itself — agents must not move their own code away.
    roots.append(Path(__file__).resolve().parents[3])
    return roots


# Same credential blocklist as ReadAnywhereSkill (computer_skill.py).
_SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", ".netrc", "credentials.json",
                    "credentials", ".npmrc", ".pypirc"}
_SENSITIVE_DIRS = {".ssh", ".gnupg", ".aws", ".azure"}


def _is_forbidden(p: Path) -> str | None:
    """Return a refusal reason, or None if the path is allowed."""
    try:
        rp = p.resolve()
    except OSError:
        return f"cannot resolve path: {p}"
    for root in _forbidden_roots():
        try:
            rp.relative_to(root.resolve())
            return f"`{rp}` is inside the protected system location `{root}`"
        except ValueError:
            continue
    if rp.name.lower() in _SENSITIVE_NAMES or rp.suffix.lower() == ".pem":
        return f"`{rp.name}` looks like a credential/secret file"
    if any(part.lower() in _SENSITIVE_DIRS for part in rp.parts):
        return f"`{rp}` is inside a credential folder"
    # Refuse drive roots as a source ("move C:\" would be catastrophic).
    if rp.parent == rp:
        return f"`{rp}` is a whole drive — refused"
    return None


def _size_of(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except (OSError, PermissionError):
            pass
    return total


def _mb(b: int) -> str:
    return f"{b / (1024 * 1024):.1f} MB"


def _plan(source: str, destination: str) -> tuple[Path, Path, str | None]:
    """Validate + normalise. Returns (src, dst, error). dst is the FINAL path
    (if destination is an existing dir, the item goes inside it)."""
    src = Path(source.strip().strip('"'))
    dst = Path(destination.strip().strip('"'))
    if not src.is_absolute() or not dst.is_absolute():
        return src, dst, "Both paths must be absolute (e.g. `C:/Users/you/Downloads/file.zip`)."
    if not src.exists():
        return src, dst, f"Source not found: `{src}`"
    for p, what in ((src, "source"), (dst, "destination")):
        reason = _is_forbidden(p)
        if reason:
            return src, dst, f"REFUSED ({what}): {reason}."
    if dst.is_dir():
        dst = dst / src.name
    # Moving a folder into itself deletes it. Refuse.
    try:
        dst.resolve().relative_to(src.resolve())
        return src, dst, f"REFUSED: destination `{dst}` is inside the source — that would destroy it."
    except ValueError:
        pass
    return src, dst, None


class MoveFileSkill(BaseSKill):
    name = "move_file"
    description = (
        "Move a file or folder to another folder or drive (e.g. C: Downloads -> "
        "E:/Games). ALWAYS call with confirm=false first: it validates and reports "
        "the plan without touching anything. Then, after the user agrees, call "
        "again with confirm=true. Never overwrites existing files unless "
        "overwrite=true is explicitly passed. System folders and credential files "
        "are refused."
    )
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Absolute path of the file/folder to move."},
            "destination": {"type": "string", "description": "Absolute destination folder (or full new path)."},
            "confirm": {"type": "boolean", "description": "False (default): plan only. True: actually move — only after the user agrees."},
            "overwrite": {"type": "boolean", "description": "Allow replacing an existing destination. Default false."},
        },
        "required": ["source", "destination"],
    }

    async def execute(self, source: str, destination: str,
                      confirm: bool = False, overwrite: bool = False, **_) -> str:
        src, dst, err = _plan(source, destination)
        if err:
            return err
        if dst.exists() and not overwrite:
            return (f"REFUSED: `{dst}` already exists. Pass overwrite=true to replace it "
                    "(ask the user first), or pick another destination.")

        size = _size_of(src)
        kind = "folder" if src.is_dir() else "file"
        if not confirm:
            free = shutil.disk_usage(dst.anchor).free
            room = "OK" if free > size else f"NOT ENOUGH SPACE (free {_mb(free)})"
            return (f"PLAN (nothing moved yet):\n"
                    f"  move {kind} `{src}` ({_mb(size)})\n"
                    f"  ->   `{dst}`\n"
                    f"  destination drive space: {room}\n"
                    f"Confirm with the user, then call move_file again with confirm=true.")

        if shutil.disk_usage(dst.anchor).free <= size:
            return f"ABORTED: not enough free space on {dst.anchor} for {_mb(size)}."
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                # Cross-drive-safe: copy, verify size, then delete the original.
                shutil.copy2(src, dst)
                if dst.stat().st_size != src.stat().st_size:
                    dst.unlink(missing_ok=True)
                    return f"ABORTED: copy verification failed for `{src.name}` — original untouched."
                src.unlink()
            else:
                if dst.exists() and overwrite:
                    shutil.rmtree(dst)
                shutil.move(str(src), str(dst))
            logger.info(f"move_file: {src} -> {dst}")
            return f"MOVED {kind} `{src.name}` ({_mb(size)}) -> `{dst}`. Original removed."
        except PermissionError:
            return f"FAILED: `{src.name}` is locked or in use (close the app using it) — nothing was lost."
        except OSError as e:
            return f"FAILED: {e} — the original is still at `{src}`."


class CopyFileSkill(BaseSKill):
    name = "copy_file"
    description = (
        "Copy a file or folder to another folder or drive, keeping the original. "
        "Same safety rules as move_file: confirm=false first to show the plan, "
        "confirm=true to copy, never overwrites without overwrite=true."
    )
    parameters = MoveFileSkill.parameters

    async def execute(self, source: str, destination: str,
                      confirm: bool = False, overwrite: bool = False, **_) -> str:
        src, dst, err = _plan(source, destination)
        if err:
            return err
        if dst.exists() and not overwrite:
            return (f"REFUSED: `{dst}` already exists. Pass overwrite=true to replace it "
                    "(ask the user first), or pick another destination.")
        size = _size_of(src)
        kind = "folder" if src.is_dir() else "file"
        if not confirm:
            return (f"PLAN (nothing copied yet):\n"
                    f"  copy {kind} `{src}` ({_mb(size)}) -> `{dst}`\n"
                    f"Confirm with the user, then call copy_file again with confirm=true.")
        if shutil.disk_usage(dst.anchor).free <= size:
            return f"ABORTED: not enough free space on {dst.anchor} for {_mb(size)}."
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy2(src, dst)
            else:
                shutil.copytree(src, dst, dirs_exist_ok=overwrite)
            logger.info(f"copy_file: {src} -> {dst}")
            return f"COPIED {kind} `{src.name}` ({_mb(size)}) -> `{dst}`. Original kept."
        except PermissionError:
            return f"FAILED: `{src.name}` is locked or in use — nothing was changed."
        except OSError as e:
            return f"FAILED: {e}"


if __name__ == "__main__":
    import asyncio, tempfile
    # Self-check: guards hold, dry-run never moves, real move works + verifies.
    async def _t():
        m = MoveFileSkill()
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        r = await m.execute(source=f"{sysroot}\\notepad.exe", destination="E:\\x")
        assert "REFUSED" in r, f"system source must be refused: {r}"
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "a.txt"; src.write_text("hi")
            dstdir = Path(td) / "sub"; dstdir.mkdir()
            r = await m.execute(source=str(src), destination=str(dstdir))
            assert "PLAN" in r and src.exists(), "dry run must not move"
            r = await m.execute(source=str(src), destination=str(dstdir), confirm=True)
            assert not src.exists() and (dstdir / "a.txt").read_text() == "hi", "move failed"
            r = await m.execute(source=str(dstdir), destination=str(dstdir / "inner"))
            assert "inside the source" in r, "self-nesting must be refused"
        print("file_ops_skill self-check ok")
    asyncio.run(_t())
