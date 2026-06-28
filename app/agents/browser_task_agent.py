"""
BrowserTaskAgent — AI observe→decide→act loop for full browser automation.

The agent:
  1. Gets page state (DOM elements + visible text + optional screenshot)
  2. Sends to LLM with task context
  3. LLM returns next JSON action
  4. Executes action
  5. Repeats until LLM says "done" or max_steps reached

Handles: Salesforce, Cisco labs, Google Workspace, any web app.
Works headed (user watches) or headless (background).

Action schema LLM must return:
  {"action": "navigate",  "url": "https://..."}
  {"action": "click",     "target": "button text or [idx] or CSS"}
  {"action": "type",      "target": "field label or [idx]", "text": "value"}
  {"action": "select",    "target": "CSS selector", "value": "option value"}
  {"action": "scroll",    "direction": "down|up", "amount": 3}
  {"action": "press",     "key": "Enter|Tab|Escape|..."}
  {"action": "wait",      "seconds": 2}
  {"action": "extract",   "target": "CSS selector"}
  {"action": "screenshot"}
  {"action": "done",      "result": "summary of what was accomplished"}
  {"action": "failed",    "reason": "why task cannot be completed"}
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator

from app.utils import logger


@dataclass
class BrowserStep:
    step: int
    action: str
    target: str = ""
    result: str = ""
    screenshot_b64: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        d = {
            "step": self.step,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "error": self.error,
        }
        if self.screenshot_b64:
            d["screenshot_b64"] = self.screenshot_b64
        return d

    def to_sse(self) -> str:
        payload = {"type": "step", "data": self.to_dict()}
        return f"data: {json.dumps(payload)}\n\n"


_SYSTEM_PROMPT = """You are an expert browser automation agent. You control a real browser to complete tasks.

RULES:
1. Reply with ONLY a single JSON action object. No explanation, no markdown.
2. Choose the most precise action. Prefer clicking visible text over CSS selectors.
3. Reference elements by their [idx] number from the elements list when possible.
4. After typing in a form field, always submit with press Enter or click the submit button.
5. If a page is loading, use {"action": "wait", "seconds": 2}.
6. If login is needed and you have credentials, use them.
7. When the task is fully complete, use {"action": "done", "result": "..."}.
8. If truly stuck after 3 attempts on same step, use {"action": "failed", "reason": "..."}.

AVAILABLE ACTIONS:
{"action": "navigate", "url": "https://..."}
{"action": "click", "target": "text or [idx] or CSS"}
{"action": "type", "target": "label or [idx]", "text": "value to type"}
{"action": "select", "target": "CSS", "value": "option"}
{"action": "scroll", "direction": "down", "amount": 3}
{"action": "press", "key": "Enter"}
{"action": "wait", "seconds": 2}
{"action": "extract", "target": "CSS or body"}
{"action": "screenshot"}
{"action": "done", "result": "task complete summary"}
{"action": "failed", "reason": "explanation"}
"""


class BrowserTaskAgent:
    name = "browser_task"
    MAX_STEPS = 50

    async def run_task(
        self,
        task: str,
        start_url: str = "",
        credentials: dict | None = None,
        headless: bool | None = None,
        capture_screenshots: bool = True,
        max_steps: int = MAX_STEPS,
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator — yields step dicts as the agent works.
        Final event has type "done" or "failed".
        """
        from app.services.browser_controller import BrowserController
        from app.services.chat_service import get_llm

        # Respect env BROWSER_HEADLESS but allow per-task override
        from app.services.browser_controller import HEADLESS
        _headless = headless if headless is not None else HEADLESS

        llm = get_llm()
        browser = BrowserController(headless=_headless)
        history: list[str] = []

        yield {"type": "start", "data": {"task": task, "headless": _headless}}

        try:
            await browser.start()

            if start_url:
                actual_url = await browser.navigate(start_url)
                yield {"type": "step", "data": {"step": 0, "action": "navigate", "target": start_url, "result": actual_url}}
                history.append(f"Step 0: navigate → {actual_url}")

            for step_num in range(1, max_steps + 1):
                # Get current page state
                state = await browser.get_state(capture_screenshot=capture_screenshots and step_num % 3 == 0)

                # Build prompt
                creds_hint = ""
                if credentials:
                    creds_hint = "\n\nAvailable credentials:\n" + "\n".join(f"  {k}: {v}" for k, v in credentials.items())

                history_text = "\n".join(history[-8:])  # last 8 steps only

                prompt = (
                    f"Task: {task}{creds_hint}\n\n"
                    f"Step {step_num}/{max_steps}\n\n"
                    f"Current page state:\n{state.to_context()}\n\n"
                    f"Actions taken so far:\n{history_text or '(none yet)'}\n\n"
                    f"What is the SINGLE next action? Reply with ONLY JSON."
                )

                # Get LLM decision
                try:
                    raw = await llm.complete(prompt, system=_SYSTEM_PROMPT)
                    action_json = _parse_action(raw)
                except Exception as e:
                    yield {"type": "step", "data": {"step": step_num, "action": "error", "error": f"LLM failed: {e}"}}
                    await asyncio.sleep(2)
                    continue

                action = action_json.get("action", "")
                target = action_json.get("target", "")
                result = ""
                screenshot_b64 = ""
                error = ""

                # Execute action
                try:
                    if action == "navigate":
                        result = await browser.navigate(action_json.get("url", ""))

                    elif action == "click":
                        ok = await browser.click(target)
                        result = "clicked" if ok else "click failed — element not found"
                        await asyncio.sleep(0.8)

                    elif action == "type":
                        ok = await browser.type_text(target, action_json.get("text", ""))
                        result = "typed" if ok else "type failed — field not found"

                    elif action == "select":
                        ok = await browser.select_option(target, action_json.get("value", ""))
                        result = "selected" if ok else "select failed"

                    elif action == "scroll":
                        await browser.scroll(
                            action_json.get("direction", "down"),
                            action_json.get("amount", 3),
                        )
                        result = "scrolled"

                    elif action == "press":
                        await browser.press_key(action_json.get("key", "Enter"))
                        result = f"pressed {action_json.get('key')}"
                        await asyncio.sleep(0.5)

                    elif action == "wait":
                        secs = float(action_json.get("seconds", 2))
                        await browser.wait_seconds(secs)
                        result = f"waited {secs}s"

                    elif action == "extract":
                        result = await browser.extract_text(target or "body")

                    elif action == "screenshot":
                        screenshot_b64 = await browser.screenshot_b64()
                        result = "screenshot taken"
                        capture_screenshots = True  # keep capturing now

                    elif action == "done":
                        final_result = action_json.get("result", "Task completed")
                        # Capture final screenshot
                        final_ss = await browser.screenshot_b64() if capture_screenshots else ""
                        yield {
                            "type": "done",
                            "data": {
                                "step": step_num,
                                "result": final_result,
                                "steps_taken": step_num,
                                "screenshot_b64": final_ss,
                            },
                        }
                        return

                    elif action == "failed":
                        yield {
                            "type": "failed",
                            "data": {
                                "step": step_num,
                                "reason": action_json.get("reason", "Unknown failure"),
                            },
                        }
                        return

                    else:
                        error = f"Unknown action: {action}"

                except Exception as e:
                    error = str(e)
                    logger.warning(f"BrowserTask step {step_num} execute error: {e}")

                # Capture screenshot every 3 steps or after navigation
                if capture_screenshots and (step_num % 3 == 0 or action == "navigate") and not screenshot_b64:
                    try:
                        screenshot_b64 = await browser.screenshot_b64()
                    except Exception:
                        pass

                step_data = {
                    "step": step_num,
                    "action": action,
                    "target": target,
                    "result": result[:300],
                    "error": error,
                }
                if screenshot_b64:
                    step_data["screenshot_b64"] = screenshot_b64

                history.append(f"Step {step_num}: {action} {target} → {result[:80]}{' ERROR: ' + error if error else ''}")
                yield {"type": "step", "data": step_data}

            # Hit max steps
            yield {"type": "failed", "data": {"reason": f"Reached max steps ({max_steps}) without completing task."}}

        except Exception as e:
            logger.error(f"BrowserTaskAgent error: {e}")
            yield {"type": "failed", "data": {"reason": str(e)}}
        finally:
            try:
                await browser.stop()
            except Exception:
                pass


def _parse_action(raw: str) -> dict:
    """Extract JSON from LLM response — handles markdown code blocks."""
    raw = raw.strip()
    # Strip markdown code block
    raw = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    # Find first { ... }
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(raw[start:end])
    raise ValueError(f"No valid JSON action in LLM response: {raw[:200]}")


_agent: BrowserTaskAgent | None = None


def get_browser_task_agent() -> BrowserTaskAgent:
    global _agent
    if _agent is None:
        _agent = BrowserTaskAgent()
    return _agent
