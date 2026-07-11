"""
illip stop — clean shutdown. Kills the ILLIP server + Ollama so nothing keeps
running in the background, then pops a Windows notification saying exactly what
was closed and warns if anything is still alive.

Standalone: only stdlib + psutil (already an ILLIP dep). Safe to run anytime.
"""

import sys
import subprocess

try:
    import psutil
except ImportError:
    print("psutil missing — run: pip install psutil")
    sys.exit(1)


def _is_illip(p) -> bool:
    try:
        cmd = " ".join(p.info.get("cmdline") or []).lower()
        return ("uvicorn" in cmd and "app.main" in cmd) or "app.main:app" in cmd
    except Exception:
        return False


def _is_ollama(p) -> bool:
    try:
        return (p.info.get("name") or "").lower().startswith("ollama")
    except Exception:
        return False


def _is_omniroute(p) -> bool:
    try:
        cmd = " ".join(p.info.get("cmdline") or []).lower()
        return "omniroute" in cmd
    except Exception:
        return False


def _scan():
    illip, ollama, omni = [], [], []
    for p in psutil.process_iter(attrs=["name", "cmdline"]):
        if _is_illip(p):
            illip.append(p)
        elif _is_ollama(p):
            ollama.append(p)
        elif _is_omniroute(p):
            omni.append(p)
    return illip, ollama, omni


def _kill(procs) -> int:
    killed = 0
    for p in procs:
        try:
            p.terminate()
            killed += 1
        except Exception:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=4)
    for p in alive:  # force any stragglers
        try:
            p.kill()
        except Exception:
            pass
    return killed


def _toast(title: str, message: str) -> None:
    """Windows toast via PowerShell — no extra module needed."""
    ps = f"""
$ErrorActionPreference='SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x=$t.GetElementsByTagName('text')
$x[0].AppendChild($t.CreateTextNode('{title}')) > $null
$x[1].AppendChild($t.CreateTextNode('{message}')) > $null
$toast=[Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ILLIP').Show($toast)
"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=10,
                       capture_output=True)
    except Exception:
        pass


def main():
    illip, ollama, omni = _scan()
    if not illip and not ollama and not omni:
        msg = "Nothing was running. All clear."
        print(msg)
        _toast("ILLIP — already stopped", msg)
        return

    n_illip = _kill(illip)
    n_ollama = _kill(ollama)
    n_omni = _kill(omni)

    # Re-scan to confirm nothing survived.
    left_illip, left_ollama, left_omni = _scan()
    parts = []
    if n_illip:
        parts.append(f"ILLIP server x{n_illip}")
    if n_ollama:
        parts.append(f"Ollama x{n_ollama}")
    if n_omni:
        parts.append(f"OmniRoute x{n_omni}")
    closed = ", ".join(parts) if parts else "nothing"

    survivors = len(left_illip) + len(left_ollama) + len(left_omni)
    if survivors:
        msg = f"Closed {closed}. WARNING: {survivors} still running — reboot to be sure."
        print(msg)
        for p in left_illip + left_ollama + left_omni:
            try:
                print(f"  still alive: pid {p.pid} {(p.info.get('name') or '')}")
            except Exception:
                pass
        _toast("ILLIP stopped — check", msg)
    else:
        msg = f"Closed {closed}. Nothing is running now."
        print(msg)
        _toast("ILLIP stopped", msg)


if __name__ == "__main__":
    main()
