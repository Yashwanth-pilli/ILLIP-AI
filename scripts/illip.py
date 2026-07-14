#!/usr/bin/env python3
"""
ILLIP AI terminal CLI — works like a local coding agent for your ILLIP instance.

Usage:
  illip "your question here"
  illip --chat          # interactive session
  illip --search "query"
  illip --skills        # list available skills
  illip --status        # system status
  illip --url http://...  # custom server (default: http://localhost:8000)
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

DEFAULT_URL = "http://localhost:8000"


def _post_stream(base_url: str, payload: dict):
    """Stream SSE tokens from /api/chat/stream. Yields text chunks."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url}/api/chat/stream",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            buffer = b""
            while True:
                chunk = resp.read(64)
                if not chunk:
                    break
                buffer += chunk
                while b"\n\n" in buffer:
                    line, buffer = buffer.split(b"\n\n", 1)
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        return
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if "token" in obj:
                        yield obj["token"]
                    elif "tool_calls" in obj:
                        names = ", ".join(obj["tool_calls"])
                        print(f"\n[Using skills: {names}]", flush=True)
                    elif "tool_result" in obj:
                        tr = obj["tool_result"]
                        print(f"[{tr['name']}]: {tr['result'][:120]}", flush=True)
                    elif "routing" in obj:
                        r = obj["routing"]
                        model = r.get("model", "?")
                        pressure = r.get("pressure", "?")
                        print(f"[{model} | hw:{pressure}] ", end="", flush=True)
    except urllib.error.URLError as e:
        print(f"\nError: Cannot connect to ILLIP at {base_url}\n  {e}", file=sys.stderr)
        sys.exit(1)


def _get(base_url: str, path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{base_url}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ask(base_url: str, message: str, force_search: bool = False):
    payload = {"message": message, "include_memory": True, "force_search": force_search}
    print()
    for token in _post_stream(base_url, payload):
        print(token, end="", flush=True)
    print("\n")


def cmd_chat(base_url: str):
    print(f"ILLIP AI — connected to {base_url}")
    print("Type your message. 'exit' or Ctrl+C to quit.\n")
    while True:
        try:
            msg = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not msg:
            continue
        if msg.lower() in ("exit", "quit", "bye"):
            print("Bye.")
            break
        print("ILLIP: ", end="", flush=True)
        cmd_ask(base_url, msg)


def cmd_status(base_url: str):
    data = _get(base_url, "/api/system/status")
    print(f"Status   : {data.get('status')}")
    print(f"Provider : {data.get('model_provider')} / {data.get('active_model')}")
    print(f"Memory   : {data.get('memory_count')} entries")
    print(f"Tasks    : {data.get('task_count')}")
    print(f"Uptime   : {data.get('uptime_seconds', 0):.0f}s")


def cmd_skills(base_url: str):
    data = _get(base_url, "/api/skills/")
    skills = data.get("skills", [])
    print(f"Available skills ({len(skills)}):")
    for s in skills:
        print(f"  {s['name']:<20} {s['description'][:70]}")


def main():
    parser = argparse.ArgumentParser(prog="illip", description="ILLIP AI CLI")
    parser.add_argument("message", nargs="?", help="Message to send")
    parser.add_argument("--chat", "-c", action="store_true", help="Interactive chat mode")
    parser.add_argument("--search", "-s", action="store_true", help="Force web search")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--skills", action="store_true", help="List available skills")
    parser.add_argument("--url", default=DEFAULT_URL, help="ILLIP server URL")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    if args.status:
        cmd_status(base_url)
    elif args.skills:
        cmd_skills(base_url)
    elif args.chat:
        cmd_chat(base_url)
    elif args.message:
        cmd_ask(base_url, args.message, force_search=args.search)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
