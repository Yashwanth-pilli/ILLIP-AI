"""
ILLIP AI CLI — install via: pip install illip-ai
Usage:
  illip start              — start the server
  illip start --host 0.0.0.0 --port 8000
  illip start --reload     — dev mode with auto-reload
  illip status             — check if server is running
  illip version            — print version
  illip build "make a snake game" --dir ./game   — run the agent crew on a folder
  illip do "add tests here"                       — build in the current folder
"""

import sys


def main():
    try:
        import click
    except ImportError:
        print("Run: pip install click")
        sys.exit(1)

    import click  # noqa: F811

    @click.group()
    def cli():
        """ILLIP AI — your AI company, in your device."""
        pass

    @cli.command()
    @click.option("--host", default=None, help="Bind host (default from .env or 127.0.0.1)")
    @click.option("--port", default=None, type=int, help="Port (default from .env or 8000)")
    @click.option("--reload", is_flag=True, help="Dev mode: auto-reload on file changes")
    @click.option("--workers", default=1, type=int, help="Number of worker processes")
    def start(host, port, reload, workers):
        """Start the ILLIP AI server."""
        try:
            import uvicorn
        except ImportError:
            click.echo("Run: pip install uvicorn[standard]")
            sys.exit(1)

        from app.config import settings
        _host = host or settings.api_host
        _port = port or settings.api_port
        click.echo(f"Starting ILLIP AI v{_get_version()} on http://{_host}:{_port}")
        click.echo("Press Ctrl+C to stop.")
        uvicorn.run(
            "app.main:app",
            host=_host,
            port=_port,
            reload=reload,
            workers=1 if reload else workers,
            log_level="info",
        )

    @cli.command()
    def status():
        """Check if ILLIP AI server is running."""
        try:
            import httpx
        except ImportError:
            click.echo("Run: pip install httpx")
            sys.exit(1)

        from app.config import settings
        url = f"http://{settings.api_host}:{settings.api_port}/api/health"
        try:
            r = httpx.get(url, timeout=3)
            d = r.json()
            click.echo(f"ILLIP AI: {d.get('status', 'unknown')} — provider: {d.get('provider', '?')}")
        except Exception:
            click.echo(f"ILLIP AI not reachable at {url}. Run: illip start")
            sys.exit(1)

    @cli.command()
    def version():
        """Print version."""
        click.echo(f"ILLIP AI {_get_version()}")

    @cli.command()
    @click.argument("task", nargs=-1, required=True)
    @click.option("--dir", "-d", "target_dir", default=".", help="Folder to build the work into (default: current dir)")
    def build(task, target_dir):
        """Run the agent crew on a folder — plans, writes files, verifies. Like a
        local coding agent working in TARGET_DIR on your own machine."""
        _run_build(click, " ".join(task), target_dir)

    @cli.command()
    @click.argument("task", nargs=-1, required=True)
    def do(task):
        """Build in the CURRENT folder. Shortcut for `illip build ... --dir .`."""
        _run_build(click, " ".join(task), ".")

    def _run_build(click, task_text, target_dir):
        import asyncio
        import logging
        from pathlib import Path
        # Windows console is cp1252; agent output may contain unicode. Reconfigure
        # stdout to utf-8 (replace on failure) so a stray emoji can't crash the run.
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        # Quiet the app logger so the CLI shows clean progress, not internal INFO spam.
        logging.getLogger("illip").setLevel(logging.WARNING)
        out = Path(target_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        # ASCII only — the Windows console (cp1252) can't encode emoji and crashes.
        click.echo(f"[ILLIP] agent crew -> {out}")
        click.echo(f"[goal] {task_text}\n")

        async def _go():
            from app.services.agent_orchestrator import run_task_stream
            n_files = 0
            async for ev in run_task_stream(task_text, out_dir=out):
                t = ev.get("type")
                if t == "plan":
                    steps = ev.get("steps", [])
                    click.echo("[plan] " + " -> ".join(s.get("agent", "?") for s in steps))
                elif t == "step_start":
                    click.echo(f"  - {ev.get('agent')}: {ev.get('task','')[:80]}")
                elif t == "files":
                    for f in ev.get("files", []):
                        n_files += 1
                        click.echo(f"    wrote {f.get('name')} ({f.get('bytes')}b)")
                elif t == "final":
                    click.echo(f"\n[done] {n_files} file(s) in {out}")
                elif t == "error":
                    click.echo(f"[error] {ev.get('message')}")

        try:
            asyncio.run(_go())
        except KeyboardInterrupt:
            click.echo("\nStopped.")
        except Exception as e:
            click.echo(f"❌ Build failed: {e}")
            click.echo("Is Ollama running? Try: illip status")
            sys.exit(1)

    @cli.command()
    def setup():
        """Install dependencies and create .env from .env.example."""
        import subprocess
        from pathlib import Path
        click.echo("Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        env = Path(".env")
        if not env.exists():
            example = Path(".env.example")
            if example.exists():
                env.write_text(example.read_text())
                click.echo(".env created from .env.example — edit it to configure your model provider.")
            else:
                click.echo("No .env.example found. Create a .env manually.")
        else:
            click.echo(".env already exists.")
        click.echo("Done. Run: illip start")

    def _get_version():
        try:
            from app import __version__
            return __version__
        except Exception:
            return "unknown"

    cli()


if __name__ == "__main__":
    main()
