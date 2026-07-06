"""
File Guardian — scan downloaded files for malicious signs, then explain
how to handle them safely (harm reduction, not "don't download").

Static analysis only — NOTHING is ever executed:
  - extension tricks (double extensions, executables disguised as documents)
  - magic-byte vs extension mismatch (an .exe pretending to be a .pdf)
  - archive inspection without extraction (executables, autorun.inf inside)
  - Windows Defender on-demand scan (native MpCmdRun, present on every Windows)
  - SHA-256 so the user can check the hash on VirusTotal themselves
    (we never upload anything — privacy first)

Used by POST /api/guardian/scan and the `/scan` chat command.
"""

import asyncio
import hashlib
import os
import zipfile
from pathlib import Path

from app.core import Message
from app.providers import get_provider
from app.utils import logger, get_current_timestamp

# Extensions that run code when double-clicked.
_EXEC_EXTS = {".exe", ".msi", ".bat", ".cmd", ".scr", ".vbs", ".vbe", ".js",
              ".jse", ".wsf", ".ps1", ".jar", ".com", ".pif", ".hta", ".cpl",
              ".dll", ".reg", ".lnk"}
# Extensions people think of as "safe documents/media".
_DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
             ".txt", ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".mkv"}

_MAX_FILES = 300          # cap for folder scans
_MAX_HASH_MB = 512        # skip hashing beyond this (repack games are huge)

_DEFENDER = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"


def _finding(level: str, message: str) -> dict:
    # level: info | warn | danger
    return {"level": level, "message": message}


def _sha256(path: Path) -> str | None:
    if path.stat().st_size > _MAX_HASH_MB * 1024 * 1024:
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _magic_kind(path: Path) -> str | None:
    """Identify real file type from leading bytes. None = unknown."""
    try:
        head = path.open("rb").read(8)
    except OSError:
        return None
    if head[:2] == b"MZ":
        return "windows-executable"
    if head[:4] == b"PK\x03\x04":
        return "zip-container"       # also docx/xlsx/jar — checked by ext below
    if head[:4] == b"%PDF":
        return "pdf"
    if head[:4] == b"\x7fELF":
        return "linux-executable"
    if head[:4] == b"Rar!":
        return "rar-archive"
    return None


def _check_file(path: Path) -> list[dict]:
    findings: list[dict] = []
    name = path.name
    suffixes = [s.lower() for s in path.suffixes]
    ext = suffixes[-1] if suffixes else ""

    # Double extension: report.pdf.exe — classic disguise.
    if len(suffixes) >= 2 and ext in _EXEC_EXTS and suffixes[-2] in _DOC_EXTS:
        findings.append(_finding("danger",
            f"`{name}` has a DOUBLE EXTENSION ({suffixes[-2]}{ext}) — an executable disguised as a document. Classic malware trick."))
    elif ext in _EXEC_EXTS:
        findings.append(_finding("warn",
            f"`{name}` is an executable ({ext}). Normal for installers, but only run it if you trust the source."))

    # Magic bytes vs extension.
    kind = _magic_kind(path)
    if kind == "windows-executable" and ext not in _EXEC_EXTS:
        findings.append(_finding("danger",
            f"`{name}` LOOKS like {ext or 'a data file'} but its content is a Windows executable. Strong malware sign."))
    if kind == "pdf" and ext in _EXEC_EXTS:
        findings.append(_finding("warn", f"`{name}` claims to be executable but starts like a PDF — corrupted or crafted."))

    # Archives: list contents WITHOUT extracting.
    if ext == ".zip" or (kind == "zip-container" and ext == ".zip"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()[:2000]
                execs = [n for n in names if Path(n).suffix.lower() in _EXEC_EXTS]
                if any(Path(n).name.lower() == "autorun.inf" for n in names):
                    findings.append(_finding("danger", f"`{name}` contains autorun.inf — auto-execution attempt on old systems."))
                doubles = [n for n in execs
                           if len(Path(n).suffixes) >= 2 and Path(n).suffixes[-2].lower() in _DOC_EXTS]
                for d in doubles[:5]:
                    findings.append(_finding("danger", f"Inside `{name}`: `{d}` — double-extension executable."))
                if execs and not doubles:
                    findings.append(_finding("info",
                        f"`{name}` contains {len(execs)} executable file(s) (normal for software/installers): "
                        + ", ".join(Path(e).name for e in execs[:5])))
                if any(zi.flag_bits & 0x1 for zi in z.infolist()[:200]):
                    findings.append(_finding("warn",
                        f"`{name}` is password-protected — often used to hide payloads from antivirus. Scan again after extracting."))
        except zipfile.BadZipFile:
            findings.append(_finding("warn", f"`{name}` has a .zip name but is not a valid zip — suspicious."))
        except Exception as e:
            findings.append(_finding("info", f"Could not inspect archive `{name}`: {e}"))
    elif kind == "rar-archive":
        findings.append(_finding("info",
            f"`{name}` is a RAR archive — cannot inspect without extracting. Extract to a folder, then `/scan` that folder before running anything."))

    return findings


async def _defender_scan(path: Path) -> dict:
    """Windows Defender on-demand scan. Exit 0 = clean, 2 = threat found."""
    if not _DEFENDER.exists():
        return _finding("info", "Windows Defender CLI not found — skipped AV scan (heuristics still apply).")
    try:
        proc = await asyncio.create_subprocess_exec(
            str(_DEFENDER), "-Scan", "-ScanType", "3", "-File", str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            return _finding("info", "Defender scan timed out (large file) — rely on heuristics + manual hash check.")
        if proc.returncode == 2:
            return _finding("danger", "**Windows Defender found a threat in this path.** It has likely quarantined it already — check Windows Security > Protection history.")
        if proc.returncode == 0:
            return _finding("info", "Windows Defender scan: clean.")
        return _finding("info", f"Defender scan inconclusive (exit {proc.returncode}).")
    except Exception as e:
        return _finding("info", f"Defender scan unavailable: {e}")


def collect_findings(target: Path) -> tuple[list[dict], list[Path]]:
    """Pure heuristics pass (no AV, no LLM) — separately testable."""
    findings: list[dict] = []
    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for f in filenames:
                files.append(Path(dirpath) / f)
                if len(files) >= _MAX_FILES:
                    findings.append(_finding("info", f"Folder has many files — scanned the first {_MAX_FILES}."))
                    break
            if len(files) >= _MAX_FILES:
                break
    for f in files:
        try:
            findings.extend(_check_file(f))
        except OSError as e:
            findings.append(_finding("info", f"Could not read `{f.name}`: {e}"))
    return findings, files


def _newest_download() -> Path | None:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return None
    entries = [p for p in downloads.iterdir() if not p.name.startswith(".")]
    return max(entries, key=lambda p: p.stat().st_mtime, default=None)


_SAFE_STEPS_FALLBACK = """
## How to handle it safely
1. **Don't run anything yet.** Scanning ≠ safe; unknown source = treat as hostile until proven otherwise.
2. **Check the hash**: copy the SHA-256 above into virustotal.com (you upload only the hash, not the file).
3. **Create a restore point**: Start > "Create a restore point" > Create. Takes 1 minute, saves your system.
4. **Test in Windows Sandbox** (free, built into Windows Pro): run the installer there first; if it misbehaves, close the sandbox and nothing touched your real system.
5. **Watch the installer**: uncheck bundled offers, refuse browser extensions, refuse "additional tools".
6. **After install**: if your browser homepage changed or ads appear, uninstall + run a full Defender scan.
"""


async def scan_path(raw_path: str | None = None) -> str:
    """Full scan -> markdown report. Empty path = newest file in Downloads."""
    if raw_path and raw_path.strip():
        target = Path(raw_path.strip().strip('"'))
    else:
        target = _newest_download()
        if target is None:
            return "Downloads folder is empty — give me a path: `/scan E:/Games/setup.exe`"

    if not target.is_absolute():
        return f"Give me an absolute path (e.g. `C:/Users/you/Downloads/{target}`)."
    if not target.exists():
        return f"Path not found: `{target}`"

    findings, files = collect_findings(target)
    findings.append(await _defender_scan(target))

    dangers = [f for f in findings if f["level"] == "danger"]
    warns = [f for f in findings if f["level"] == "warn"]

    if dangers:
        verdict = "🔴 **HIGH RISK** — malicious signs found. Do not run anything from this path yet."
    elif warns:
        verdict = "🟡 **CAUTION** — nothing confirmed malicious, but handle carefully."
    else:
        verdict = "🟢 **No malicious signs found.** (No scan is a guarantee — follow the safe steps for anything from an untrusted source.)"

    lines = [f"# 🛡️ Guardian scan: `{target.name}`", "", verdict, "",
             f"Scanned **{len(files)} file(s)**.", ""]
    if dangers or warns:
        lines.append("## Findings")
        for f in dangers + warns:
            icon = "🔴" if f["level"] == "danger" else "🟡"
            lines.append(f"- {icon} {f['message']}")
        lines.append("")
    infos = [f for f in findings if f["level"] == "info"]
    if infos:
        lines.append("## Notes")
        lines.extend(f"- {f['message']}" for f in infos)
        lines.append("")

    # Hashes for manual VirusTotal lookup (privacy: hash only, never the file).
    hash_lines = []
    for f in files[:5]:
        try:
            h = _sha256(f)
            hash_lines.append(f"- `{f.name}`: `{h}`" if h else f"- `{f.name}`: too large to hash locally")
        except OSError:
            pass
    if hash_lines:
        lines += ["## SHA-256 (paste into virustotal.com to cross-check)", *hash_lines, ""]

    # LLM turns findings into tailored safe-handling steps; static fallback otherwise.
    try:
        provider = await get_provider()
        prompt = (
            f"A user scanned a download before installing it. Target: {target.name}. "
            f"Findings: {[f['message'] for f in findings]}. "
            "Write a short, numbered, practical guide for installing/opening this safely on Windows "
            "(restore point, Windows Sandbox or a VM for testing, what to watch for during install, "
            "what to do if the AV flagged it). Do NOT lecture them about downloading — pure harm reduction. "
            "Max 8 steps, markdown, start with heading '## How to handle it safely'."
        )
        advice = await provider.generate_response(
            [Message(role="user", content=prompt, timestamp=get_current_timestamp())],
            temperature=0.3,
        )
        lines.append(advice.strip() if advice and advice.strip() else _SAFE_STEPS_FALLBACK)
    except Exception as e:
        logger.debug(f"guardian LLM advice unavailable: {e}")
        lines.append(_SAFE_STEPS_FALLBACK)

    return "\n".join(lines)
