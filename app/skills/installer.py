"""
Skill + Connector installer — install from any URL, zero disk waste.

Supported URL types:
  - Raw Python file URL  → fetched into memory, exec'd, registered. No disk write.
  - GitHub repo URL      → cloned to temp dir, registered, then offers cleanup.
  - PyPI package name    → pip install, then import and register.

Flow:
  install_from_url(url) → InstallResult
    .installed     bool
    .names         list of skill/connector names registered
    .cleanup_needed  bool — True if temp dir was created
    .temp_path     str | None — path to delete if cleanup_needed
    .prompt        str — message to show user ("Keep folder or delete?")
"""

import asyncio
import importlib
import importlib.util
import inspect
import os
import shutil
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.utils import logger


@dataclass
class InstallResult:
    installed: bool
    names: list[str] = field(default_factory=list)
    cleanup_needed: bool = False
    temp_path: str | None = None
    prompt: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "installed": self.installed,
            "names": self.names,
            "cleanup_needed": self.cleanup_needed,
            "temp_path": self.temp_path,
            "prompt": self.prompt,
            "error": self.error,
        }


def _find_and_register_classes(mod: types.ModuleType) -> list[str]:
    """Scan module for BaseSKill / BaseConnector subclasses and register them."""
    from app.skills.base_skill import BaseSKill
    from app.skills.registry import get_registry
    from app.connectors.base_connector import BaseConnector
    from app.connectors.registry import get_connector_registry

    registered = []

    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if cls.__module__ != mod.__name__ and cls.__module__ != "__exec__":
            continue  # skip imported base classes

        # Skill
        if issubclass(cls, BaseSKill) and cls is not BaseSKill:
            try:
                instance = cls()
                get_registry().register(instance)
                registered.append(f"skill:{instance.name}")
                logger.info(f"URL-installed skill: {instance.name}")
            except Exception as e:
                logger.warning(f"Skill class {cls.__name__} failed to instantiate: {e}")

        # Connector
        if issubclass(cls, BaseConnector) and cls is not BaseConnector:
            try:
                instance = cls()
                get_connector_registry()._connectors[instance.name] = instance
                registered.append(f"connector:{instance.name}")
                logger.info(f"URL-installed connector: {instance.name}")
            except Exception as e:
                logger.warning(f"Connector class {cls.__name__} failed to instantiate: {e}")

    return registered


async def _install_raw_file(url: str) -> InstallResult:
    """Fetch a single .py file, exec in memory, register. Zero disk write."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            code = r.text
    except Exception as e:
        return InstallResult(installed=False, error=f"Fetch failed: {e}")

    mod_name = Path(url.split("?")[0]).stem
    mod = types.ModuleType(mod_name)
    mod.__name__ = "__exec__"
    try:
        exec(compile(code, url, "exec"), mod.__dict__)  # noqa: S102
    except Exception as e:
        return InstallResult(installed=False, error=f"Exec failed: {e}")

    sys.modules[mod_name] = mod
    names = _find_and_register_classes(mod)

    if not names:
        return InstallResult(installed=False, error="No BaseSKill or BaseConnector subclass found in file.")

    return InstallResult(
        installed=True,
        names=names,
        cleanup_needed=False,
        prompt=f"Skill/connector '{', '.join(names)}' integrated from URL. No files saved to disk.",
    )


async def _install_github_repo(repo_url: str) -> InstallResult:
    """Clone repo to temp dir, find + register skills/connectors, offer cleanup."""
    tmp = tempfile.mkdtemp(prefix="illip_skill_")
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth=1", repo_url, tmp,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return InstallResult(installed=False, error=f"git clone failed: {stderr.decode()[:300]}")
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return InstallResult(installed=False, error=f"git not found or clone error: {e}")

    # Install requirements if present
    req_file = Path(tmp) / "requirements.txt"
    if req_file.exists():
        proc2 = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc2.communicate()

    # Find skill .py files (look for skill.py, connector.py, or any .py in root/src)
    search_dirs = [Path(tmp), Path(tmp) / "src", Path(tmp) / "skill", Path(tmp) / "connector"]
    py_files = []
    for d in search_dirs:
        if d.exists():
            py_files.extend(d.glob("*.py"))

    registered: list[str] = []
    for py_file in py_files:
        if py_file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
        if not spec:
            continue
        mod = importlib.util.module_from_spec(spec)
        mod.__name__ = "__exec__"
        try:
            spec.loader.exec_module(mod)
            registered.extend(_find_and_register_classes(mod))
        except Exception as e:
            logger.debug(f"Skipping {py_file.name}: {e}")

    if not registered:
        shutil.rmtree(tmp, ignore_errors=True)
        return InstallResult(installed=False, error="No BaseSKill or BaseConnector subclass found in repo.")

    names_str = ", ".join(registered)
    return InstallResult(
        installed=True,
        names=registered,
        cleanup_needed=True,
        temp_path=tmp,
        prompt=(
            f"Skill '{names_str}' integrated from GitHub repo. "
            f"Downloaded folder at {tmp}. Keep it or delete to save space?"
        ),
    )


async def _install_pypi(package: str) -> InstallResult:
    """pip install a package, then auto-discover skill/connector classes."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", package, "-q",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        return InstallResult(installed=False, error=f"pip install failed: {stderr.decode()[:300]}")

    # Try to import the package and scan for classes
    pkg_name = package.split(">=")[0].split("==")[0].split("[")[0].replace("-", "_")
    try:
        mod = importlib.import_module(pkg_name)
        registered = _find_and_register_classes(mod)
    except ImportError:
        registered = []

    return InstallResult(
        installed=True,
        names=registered or [f"package:{pkg_name}"],
        cleanup_needed=False,
        prompt=f"Package '{package}' installed. {'Classes registered: ' + str(registered) if registered else 'No auto-registered classes found — import manually.'}",
    )


async def install_from_url(url: str) -> InstallResult:
    """
    Main entry point. Auto-detects URL type and installs.

    Supports:
      https://raw.githubusercontent.com/.../*.py  → memory exec, no disk
      https://github.com/user/repo                → git clone, cleanup prompt
      pypi:some-package                           → pip install
    """
    url = url.strip()

    if url.startswith("pypi:"):
        return await _install_pypi(url[5:].strip())

    if url.endswith(".py") or "raw.githubusercontent.com" in url or "/raw/" in url:
        return await _install_raw_file(url)

    if "github.com" in url or url.endswith(".git"):
        return await _install_github_repo(url)

    # Try as raw file first, fall back to GitHub repo
    if url.startswith("http"):
        result = await _install_raw_file(url)
        if result.installed:
            return result
        return await _install_github_repo(url)

    return InstallResult(installed=False, error=f"Cannot determine install type for: {url}")


async def cleanup_temp(temp_path: str) -> bool:
    """Delete downloaded temp folder after user confirms."""
    try:
        shutil.rmtree(temp_path, ignore_errors=False)
        logger.info(f"Cleaned up temp dir: {temp_path}")
        return True
    except Exception as e:
        logger.error(f"Cleanup failed for {temp_path}: {e}")
        return False


def save_to_user_connectors(url: str, code: str) -> str:
    """
    Optionally persist a URL-fetched skill to data/connectors/ so it
    survives restarts. Returns the saved path.
    """
    from app.config import settings
    dest_dir = settings.get_data_path() / "connectors"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(url.split("?")[0]).stem
    dest = dest_dir / f"{name}.py"
    dest.write_text(code)
    return str(dest)
