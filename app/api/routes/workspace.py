from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body
from pypdf import PdfReader

from app.config import settings
from app.core import Message
from app.core.schemas import WorkspaceUploadResponse
from app.providers import get_provider
from app.services.workspace_service import get_workspace_service


router = APIRouter(
    prefix="/workspace",
    tags=["workspace"]
)


SKIP_DIR_NAMES = {".git", ".venv", "__pycache__", "node_modules"}

PREVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".php", ".rb",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".md", ".txt", ".rst",
    ".csv", ".xml",
    ".pdf",
}

TEXT_BASED_EXTENSIONS = PREVIEWABLE_EXTENSIONS - {".pdf"}


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def get_workspace_files_recursive(workspace_path: Path) -> List[Path]:
    files = []

    for item in workspace_path.rglob("*"):
        if should_skip_path(item):
            continue

        if item.is_file():
            files.append(item)

    return files


def get_relative_file_name(workspace_path: Path, file_path: Path) -> str:
    return str(file_path.relative_to(workspace_path)).replace("\\", "/")


def resolve_workspace_file(workspace_path: Path, relative_path: str) -> Path:
    requested_path = (workspace_path / relative_path).resolve()
    workspace_root = workspace_path.resolve()

    if workspace_root not in requested_path.parents and requested_path != workspace_root:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if should_skip_path(requested_path):
        raise HTTPException(status_code=400, detail="Access to this path is not allowed")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return requested_path


def detect_project_type(workspace_path: Path) -> Dict[str, Any]:
    files = get_workspace_files_recursive(workspace_path)

    file_types: Dict[str, int] = {}
    detected_features = set()

    for item in files:
        suffix = item.suffix.lower()
        if not suffix:
            suffix = "no_extension"

        file_types[suffix] = file_types.get(suffix, 0) + 1

    total_files = len(files)
    file_names = {file.name.lower() for file in files}

    py_files = [file for file in files if file.suffix.lower() == ".py"]
    html_files = [file for file in files if file.suffix.lower() == ".html"]
    css_files = [file for file in files if file.suffix.lower() == ".css"]
    js_files = [file for file in files if file.suffix.lower() == ".js"]
    pdf_files = [file for file in files if file.suffix.lower() == ".pdf"]

    has_requirements = "requirements.txt" in file_names
    has_package_json = "package.json" in file_names
    has_pyproject = "pyproject.toml" in file_names
    has_poetry_lock = "poetry.lock" in file_names
    has_pnpm_lock = "pnpm-lock.yaml" in file_names
    has_package_lock = "package-lock.json" in file_names
    has_yarn_lock = "yarn.lock" in file_names
    has_dockerfile = "dockerfile" in file_names
    has_docker_compose = (
        "docker-compose.yml" in file_names or
        "docker-compose.yaml" in file_names or
        "compose.yml" in file_names or
        "compose.yaml" in file_names
    )
    has_env_example = ".env.example" in file_names
    has_github_actions = any(".github/workflows" in str(file).replace("\\", "/") for file in files)
    has_readme_only = total_files == 1 and "readme.md" in file_names
    has_frontend_combo = (
        "index.html" in file_names and
        "styles.css" in file_names and
        "app.js" in file_names
    )

    if py_files:
        detected_features.add("Python")

    if has_package_json:
        detected_features.add("Node.js")

    if html_files or css_files or js_files or has_frontend_combo:
        detected_features.add("Frontend")

    if pdf_files and total_files == len(pdf_files):
        detected_features.add("Documents")

    if has_pyproject:
        detected_features.add("pyproject")

    if has_poetry_lock:
        detected_features.add("Poetry")

    if has_package_lock or has_yarn_lock or has_pnpm_lock:
        detected_features.add("JavaScript Lockfile")

    if has_dockerfile or has_docker_compose:
        detected_features.add("Docker")

    if has_env_example:
        detected_features.add("Environment Template")

    if has_github_actions:
        detected_features.add("GitHub Actions")

    fastapi_detected = False

    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if (
                "from fastapi import" in content or
                "import fastapi" in content or
                "FastAPI(" in content
            ):
                fastapi_detected = True
                detected_features.add("FastAPI")
                break
        except Exception:
            continue

    project_type = "Unknown Project"

    if fastapi_detected and ("main.py" in file_names or py_files):
        project_type = "FastAPI Project"
    elif has_frontend_combo:
        project_type = "Frontend Project"
    elif has_package_json:
        project_type = "Node.js Project"
    elif py_files or has_requirements or has_pyproject:
        project_type = "Python Project"
    elif has_readme_only:
        project_type = "Documentation Project"
    elif pdf_files and total_files == len(pdf_files):
        project_type = "Document Collection"

    return {
        "project_type": project_type,
        "total_files": total_files,
        "file_types": file_types,
        "detected_features": sorted(detected_features),
    }


def build_workspace_summary(analysis: Dict[str, Any]) -> str:
    file_types = analysis.get("file_types", {})
    detected_features = analysis.get("detected_features", [])

    file_types_text = ", ".join(
        f"{ext}: {count}" for ext, count in sorted(file_types.items())
    ) or "No files detected"

    features_text = ", ".join(detected_features) or "None"

    return (
        f"Project type: {analysis.get('project_type', 'Unknown Project')}\n"
        f"Total files: {analysis.get('total_files', 0)}\n"
        f"File types: {file_types_text}\n"
        f"Detected features: {features_text}"
    )


async def generate_ai_workspace_analysis(summary: str) -> Optional[str]:
    try:
        provider = await get_provider()

        messages = [
            Message(
                role="system",
                content=(
                    "You are analyzing a developer workspace. "
                    "Give a concise but useful technical assessment."
                ),
                timestamp=datetime.now(),
            ),
            Message(
                role="user",
                content=(
                    "Analyze this workspace and explain what kind of project it appears to be. "
                    "Mention technologies used, possible purpose, strengths, weaknesses, "
                    "and recommendations.\n\n"
                    f"Workspace summary:\n{summary}"
                ),
                timestamp=datetime.now(),
            ),
        ]

        response = await provider.generate_response(messages=messages)

        if not response:
            return None

        if isinstance(response, str):
            ai_text = response.strip()
        elif hasattr(response, "content"):
            ai_text = str(response.content).strip()
        elif isinstance(response, dict):
            ai_text = (
                response.get("content")
                or response.get("response")
                or response.get("text")
                or response.get("message")
                or ""
            ).strip()
        else:
            ai_text = str(response).strip()

        if not ai_text:
            return None

        if ai_text.startswith("Error:"):
            return None

        return ai_text

    except Exception:
        return None


async def generate_ai_file_explanation(file_name: str, file_content: str) -> Optional[str]:
    try:
        provider = await get_provider()

        messages = [
            Message(
                role="system",
                content=(
                    "You explain developer files clearly and concisely. "
                    "Summarize purpose, key logic, risks, and suggested improvements."
                ),
                timestamp=datetime.now(),
            ),
            Message(
                role="user",
                content=(
                    f"Explain this file:\n\nFile: {file_name}\n\nContent:\n{file_content[:12000]}"
                ),
                timestamp=datetime.now(),
            ),
        ]

        response = await provider.generate_response(messages=messages)

        if not response:
            return None

        if isinstance(response, str):
            result = response.strip()
        elif hasattr(response, "content"):
            result = str(response.content).strip()
        elif isinstance(response, dict):
            result = (
                response.get("content")
                or response.get("response")
                or response.get("text")
                or response.get("message")
                or ""
            ).strip()
        else:
            result = str(response).strip()

        if not result or result.startswith("Error:"):
            return None

        return result
    except Exception:
        return None


async def generate_ai_project_explanation(project_summary: str, dependency_summary: Dict[str, Any], health_summary: Dict[str, Any]) -> Optional[str]:
    try:
        provider = await get_provider()

        messages = [
            Message(
                role="system",
                content=(
                    "You explain software projects like a technical architect. "
                    "Be concise, practical, and beginner-friendly."
                ),
                timestamp=datetime.now(),
            ),
            Message(
                role="user",
                content=(
                    "Explain this project clearly.\n\n"
                    f"Project summary:\n{project_summary}\n\n"
                    f"Dependencies:\n{dependency_summary}\n\n"
                    f"Health:\n{health_summary}"
                ),
                timestamp=datetime.now(),
            ),
        ]

        response = await provider.generate_response(messages=messages)

        if not response:
            return None

        if isinstance(response, str):
            result = response.strip()
        elif hasattr(response, "content"):
            result = str(response.content).strip()
        elif isinstance(response, dict):
            result = (
                response.get("content")
                or response.get("response")
                or response.get("text")
                or response.get("message")
                or ""
            ).strip()
        else:
            result = str(response).strip()

        if not result or result.startswith("Error:"):
            return None

        return result
    except Exception:
        return None


def is_previewable_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in PREVIEWABLE_EXTENSIONS


def is_text_based_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in TEXT_BASED_EXTENSIONS


def extract_text_preview(file_path: Path, limit: int = 2000) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def extract_pdf_preview(file_path: Path, limit: int = 2000) -> str:
    try:
        reader = PdfReader(str(file_path))
        parts: List[str] = []

        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            if text:
                parts.append(text)

            joined = "\n".join(parts)
            if len(joined) >= limit:
                return joined[:limit]

        return "\n".join(parts)[:limit]
    except Exception:
        return ""


def extract_file_preview(file_path: Path, limit: int = 2000) -> str:
    if file_path.suffix.lower() == ".pdf":
        return extract_pdf_preview(file_path, limit=limit)

    return extract_text_preview(file_path, limit=limit)


def get_workspace_file_summaries(workspace_path: Path) -> Dict[str, Any]:
    files_data = []

    for item in get_workspace_files_recursive(workspace_path):
        if not is_previewable_file(item):
            continue

        preview = extract_file_preview(item, limit=2000)

        files_data.append({
            "name": get_relative_file_name(workspace_path, item),
            "type": item.suffix.lower() or "no_extension",
            "preview": preview,
        })

    return {
        "files": files_data
    }


def get_workspace_file_content(workspace_path: Path, relative_path: str) -> Dict[str, Any]:
    file_path = resolve_workspace_file(workspace_path, relative_path)

    if not is_previewable_file(file_path):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = extract_file_preview(file_path, limit=200000)

    return {
        "name": get_relative_file_name(workspace_path, file_path),
        "type": file_path.suffix.lower() or "no_extension",
        "content": content,
    }


def search_workspace_files(workspace_path: Path, query: str, limit: int = 50) -> Dict[str, Any]:
    query_lower = query.lower()
    matches = []

    for item in get_workspace_files_recursive(workspace_path):
        relative_name = get_relative_file_name(workspace_path, item)
        name_match = query_lower in relative_name.lower()

        preview = ""
        content_match = False

        if is_previewable_file(item):
            preview = extract_file_preview(item, limit=4000)
            if preview:
                content_match = query_lower in preview.lower()

        if name_match or content_match:
            matches.append({
                "name": relative_name,
                "type": item.suffix.lower() or "no_extension",
                "match_type": "name" if name_match and not content_match else "content" if content_match and not name_match else "name_and_content",
                "preview": preview[:2000],
            })

        if len(matches) >= limit:
            break

    return {
        "query": query,
        "count": len(matches),
        "results": matches,
    }


def parse_python_dependencies(file_path: Path) -> List[str]:
    dependencies = []

    try:
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            dependencies.append(cleaned)
    except Exception:
        return []

    return dependencies


def parse_json_dependencies(file_path: Path) -> Dict[str, List[str]]:
    import json

    try:
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {"dependencies": [], "devDependencies": []}

    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("devDependencies", {}) or {}

    return {
        "dependencies": sorted([f"{name}: {version}" for name, version in deps.items()]),
        "devDependencies": sorted([f"{name}: {version}" for name, version in dev_deps.items()]),
    }


def get_workspace_dependencies(workspace_path: Path) -> Dict[str, Any]:
    python_dependencies: List[str] = []
    node_dependencies: List[str] = []
    node_dev_dependencies: List[str] = []
    manifests: List[str] = []

    for item in get_workspace_files_recursive(workspace_path):
        relative_name = get_relative_file_name(workspace_path, item)
        lower_name = item.name.lower()

        if lower_name == "requirements.txt":
            manifests.append(relative_name)
            python_dependencies.extend(parse_python_dependencies(item))

        elif lower_name == "package.json":
            manifests.append(relative_name)
            parsed = parse_json_dependencies(item)
            node_dependencies.extend(parsed["dependencies"])
            node_dev_dependencies.extend(parsed["devDependencies"])

        elif lower_name in {
            "pyproject.toml", "poetry.lock", "package-lock.json",
            "pnpm-lock.yaml", "yarn.lock", "dockerfile",
            "docker-compose.yml", "docker-compose.yaml",
            "compose.yml", "compose.yaml", ".env.example"
        }:
            manifests.append(relative_name)

    return {
        "manifests": sorted(set(manifests)),
        "python_dependencies": sorted(set(python_dependencies)),
        "node_dependencies": sorted(set(node_dependencies)),
        "node_dev_dependencies": sorted(set(node_dev_dependencies)),
    }


def get_workspace_health(workspace_path: Path) -> Dict[str, Any]:
    files = get_workspace_files_recursive(workspace_path)
    file_names = {file.name.lower() for file in files}
    warnings = []
    info = []

    if not files:
        warnings.append("Workspace is empty")

    if "readme.md" not in file_names:
        warnings.append("README.md is missing")

    if "requirements.txt" not in file_names and "pyproject.toml" not in file_names and "package.json" not in file_names:
        warnings.append("No common dependency manifest found")

    if ".env" in file_names and ".env.example" not in file_names:
        warnings.append(".env exists but .env.example is missing")

    if "dockerfile" in file_names:
        info.append("Dockerfile detected")

    if any(file.stat().st_size > 5 * 1024 * 1024 for file in files if file.is_file()):
        warnings.append("Large files detected (>5MB)")

    return {
        "total_files": len(files),
        "warnings": warnings,
        "info": info,
        "status": "healthy" if not warnings else "needs_attention",
    }


@router.get("/status")
async def workspace_status():
    """Simple workspace status endpoint"""
    return {
        "status": "ready",
        "message": "Workspace system initialized"
    }


@router.get("/list")
async def list_workspaces():
    """List files in workspace directory"""
    workspace_path = settings.get_workspaces_path()

    files = []

    for item in get_workspace_files_recursive(workspace_path):
        files.append(get_relative_file_name(workspace_path, item))

    return {
        "files": files,
        "count": len(files),
    }


@router.get("/tree")
async def workspace_tree():
    """Get workspace directory structure"""
    workspace_path = settings.get_workspaces_path()

    items = []

    for item in workspace_path.rglob("*"):
        if should_skip_path(item):
            continue

        items.append({
            "name": str(item.relative_to(workspace_path)).replace("\\", "/"),
            "type": "directory" if item.is_dir() else "file"
        })

    return {
        "workspace": workspace_path.name,
        "items": items,
    }


@router.get("/analyze")
async def analyze_workspace():
    """Analyze workspace contents and detect project type"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Workspace directory not found"
        )

    try:
        return detect_project_type(workspace_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze workspace: {str(exc)}"
        ) from exc


@router.get("/analyze-ai")
async def analyze_workspace_ai():
    """Analyze workspace contents and generate AI explanation"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Workspace directory not found"
        )

    try:
        analysis = detect_project_type(workspace_path)
        summary = build_workspace_summary(analysis)
        ai_analysis = await generate_ai_workspace_analysis(summary)

        if ai_analysis is None:
            return {
                "project_type": analysis["project_type"],
                "ai_analysis": None,
                "provider_status": "failed",
                "error": "Ollama generation failed",
                "detected_features": analysis["detected_features"],
            }

        return {
            "project_type": analysis["project_type"],
            "ai_analysis": ai_analysis,
            "provider_status": "ok",
            "error": None,
            "detected_features": analysis["detected_features"],
        }

    except HTTPException:
        raise
    except Exception:
        return {
            "project_type": "Unknown Project",
            "ai_analysis": None,
            "provider_status": "failed",
            "error": "Ollama generation failed",
            "detected_features": [],
        }


@router.get("/file-summary")
async def workspace_file_summary():
    """List workspace files with previews for supported developer workspace files"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Workspace directory not found"
        )

    try:
        return get_workspace_file_summaries(workspace_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate workspace file summary: {str(exc)}"
        ) from exc


@router.get("/file-content")
async def workspace_file_content(path: str = Query(..., description="Relative file path inside workspace")):
    """Read full content of a supported workspace file"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        return get_workspace_file_content(workspace_path, path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read workspace file: {str(exc)}"
        ) from exc


@router.get("/search")
async def workspace_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=200)
):
    """Search workspace files by file name and file content"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        return search_workspace_files(workspace_path, q, limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search workspace: {str(exc)}"
        ) from exc


@router.get("/dependencies")
async def workspace_dependencies():
    """Extract dependency-related information from workspace manifests"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        return get_workspace_dependencies(workspace_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract dependencies: {str(exc)}"
        ) from exc


@router.get("/health")
async def workspace_health():
    """Report basic workspace health diagnostics"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        return get_workspace_health(workspace_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze workspace health: {str(exc)}"
        ) from exc


@router.get("/explain-file")
async def workspace_explain_file(path: str = Query(..., description="Relative file path inside workspace")):
    """Generate AI explanation for a single workspace file"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        file_data = get_workspace_file_content(workspace_path, path)
        explanation = await generate_ai_file_explanation(file_data["name"], file_data["content"])

        if explanation is None:
            return {
                "name": file_data["name"],
                "type": file_data["type"],
                "explanation": None,
                "provider_status": "failed",
                "error": "AI explanation failed",
            }

        return {
            "name": file_data["name"],
            "type": file_data["type"],
            "explanation": explanation,
            "provider_status": "ok",
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to explain file: {str(exc)}"
        ) from exc


@router.get("/explain-project")
async def workspace_explain_project():
    """Generate AI explanation for the whole project"""
    workspace_path = settings.get_workspaces_path()

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    try:
        analysis = detect_project_type(workspace_path)
        summary = build_workspace_summary(analysis)
        dependencies = get_workspace_dependencies(workspace_path)
        health = get_workspace_health(workspace_path)
        explanation = await generate_ai_project_explanation(summary, dependencies, health)

        if explanation is None:
            return {
                "project_type": analysis["project_type"],
                "explanation": None,
                "provider_status": "failed",
                "error": "AI project explanation failed",
                "detected_features": analysis["detected_features"],
            }

        return {
            "project_type": analysis["project_type"],
            "explanation": explanation,
            "provider_status": "ok",
            "error": None,
            "detected_features": analysis["detected_features"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to explain project: {str(exc)}"
        ) from exc


def _safe_upload_name(name: str) -> str:
    import re as _re
    name = (name or "uploaded_file").replace("\\", "/").split("/")[-1]
    return _re.sub(r"[^\w. ()\[\]-]", "_", name)[:150] or "uploaded_file"


def _extract_zip_safe(zip_path: Path, dest: Path) -> list[str]:
    """Extract a zip, refusing path-traversal entries. Returns extracted names."""
    import zipfile
    extracted: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if not str(target).startswith(str(dest.resolve())):
                continue  # zip-slip entry — skip
            z.extract(info, dest)
            if not info.is_dir():
                extracted.append(info.filename)
    return extracted


@router.post("/upload")
async def upload_workspace(file: UploadFile = File(...), extract: bool = Query(True)):
    """Upload ANY file, any size. Streams to disk in chunks (no RAM limit).
    Zip files are auto-extracted into a folder named after the archive."""
    workspace_path = settings.get_workspaces_path()
    workspace_path.mkdir(parents=True, exist_ok=True)

    filename = _safe_upload_name(file.filename)
    save_path = workspace_path / filename
    # Never overwrite: report_2.pdf, report_3.pdf, ...
    if save_path.exists():
        stem, dot, ext = filename.rpartition(".")
        n = 2
        while save_path.exists():
            filename = f"{stem}_{n}.{ext}" if dot else f"{filename}_{n}"
            save_path = workspace_path / filename
            n += 1

    size = 0
    try:
        with open(save_path, "wb") as f:
            while chunk := await file.read(8 * 1024 * 1024):  # 8 MB chunks
                f.write(chunk)
                size += len(chunk)
    except Exception as exc:
        try:
            save_path.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    extracted: list[str] = []
    if extract and filename.lower().endswith(".zip"):
        try:
            extract_dir = workspace_path / filename.rsplit(".", 1)[0]
            extracted = _extract_zip_safe(save_path, extract_dir)
        except Exception as exc:
            # keep the zip itself even if extraction fails
            extracted = [f"(extract failed: {exc})"]

    return {
        "filename": filename,
        "saved_path": str(save_path),
        "size_bytes": size,
        "extracted_files": extracted[:200],
        "extracted_count": len([e for e in extracted if not e.startswith("(")]),
        "uploaded_at": datetime.now().isoformat(),
        "status": "uploaded",
    }


# ── WorkspaceService intelligence endpoints ──────────────────────────────────

@router.post("/workspaces")
async def create_workspace(
    name: str = Body(..., embed=True),
    path: str = Body("", embed=True),
    description: str = Body("", embed=True),
):
    """Create a named workspace pointing at a directory on disk."""
    svc = get_workspace_service()
    return svc.create_workspace(name, path, description)


@router.get("/workspaces")
async def list_workspaces_svc():
    """List all named workspaces managed by WorkspaceService."""
    svc = get_workspace_service()
    return svc.list_workspaces()


@router.get("/workspaces/current")
async def get_current_workspace():
    """Return currently active workspace."""
    svc = get_workspace_service()
    ws = svc.get_current_workspace()
    if ws is None:
        return {"workspace": None}
    return {"workspace": ws}


@router.put("/workspaces/current/{workspace_id}")
async def switch_workspace(workspace_id: str):
    """Switch active workspace by ID."""
    svc = get_workspace_service()
    ok = svc.set_current_workspace(workspace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"switched": workspace_id}


@router.get("/workspaces/stats")
async def workspace_svc_stats():
    """File count, size, language breakdown of current workspace."""
    svc = get_workspace_service()
    return svc.get_stats()


@router.get("/intel/files")
async def intel_list_files(
    path: str = Query("", description="Override workspace root path"),
    max_files: int = Query(200, ge=1, le=2000),
):
    """List all text files in workspace (WorkspaceService)."""
    svc = get_workspace_service()
    files = svc.list_files(workspace_path=path, max_files=max_files)
    return {"files": files, "count": len(files)}


@router.get("/intel/search")
async def intel_search_files(
    q: str = Query(..., description="Search query string"),
    path: str = Query("", description="Override workspace root path"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Grep-style search across workspace files."""
    svc = get_workspace_service()
    results = svc.search_files(query=q, workspace_path=path, max_results=max_results)
    return {"query": q, "count": len(results), "results": results}


@router.get("/intel/read")
async def intel_read_file(
    file: str = Query(..., description="Relative file path within workspace"),
    path: str = Query("", description="Override workspace root path"),
):
    """Read a single file from workspace (max 64 KB)."""
    svc = get_workspace_service()
    result = svc.read_file(rel_path=file, workspace_path=path)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/intel/context")
async def intel_get_context(
    q: str = Query(..., description="Query — finds most relevant files"),
    path: str = Query("", description="Override workspace root path"),
    max_files: int = Query(5, ge=1, le=20),
):
    """Return keyword-scored relevant file context for injection into chat."""
    svc = get_workspace_service()
    ctx = svc.get_relevant_context(query=q, workspace_path=path, max_files=max_files)
    return {"query": q, "context": ctx, "empty": not ctx}