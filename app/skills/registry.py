"""
SkillRegistry — central registry for all plugins/skills.
"""

from typing import Dict
from app.skills.base_skill import BaseSKill
from app.utils import logger


# Skills that can change or damage the system. In supervised mode these are
# gated by the 'high_risk_tool' governance policy (default: require approval).
HIGH_RISK_SKILLS = {"run_shell", "run_python", "move_file", "clean_junk", "install_package"}


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, BaseSKill] = {}

    def register(self, skill: BaseSKill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Skill registered: {skill.name}")

    def get(self, name: str) -> BaseSKill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    def to_tool_specs(self) -> list[dict]:
        return [s.to_tool_spec() for s in self._skills.values()]

    async def run(self, name: str, args: dict) -> str:
        # Supervised gate: high-risk skills need approval before they execute.
        if name in HIGH_RISK_SKILLS:
            from app.governance.manager import get_governance_manager
            decision = get_governance_manager().gate_tool(name, args or {})
            if decision.get("level") == "block":
                return f"🚫 Blocked by policy: `{name}` is not allowed. Change it in Governance if you meant to."
            if not decision.get("allowed"):
                rid = decision.get("request_id")
                summ = self._summarize(name, args or {})
                return (f"⏸️ **Approval needed** — ILLIP wants to run `{name}`{summ}.\n"
                        f"Approve: `/approve {rid}`   ·   Deny: `/deny {rid}`")
        return await self._run_now(name, args)

    async def _run_now(self, name: str, args: dict) -> str:
        skill = self._skills.get(name)
        if not skill:
            return f"Error: skill '{name}' not found. Available: {list(self._skills)}"
        try:
            result = await skill.execute(**(args or {}))
            logger.info(f"Skill '{name}' executed -> {str(result)[:80]}")
            return result
        except Exception as e:
            logger.error(f"Skill '{name}' failed: {e}")
            return f"Error running skill '{name}': {e}"

    async def execute_approved(self, request_id: str) -> str:
        """Run a skill that the user approved (bypasses the gate — already vetted)."""
        from app.governance.manager import get_governance_manager
        payload = get_governance_manager().take_approved(request_id)
        if not payload:
            return f"No approved action `{request_id}` (already run, denied, or unknown)."
        return await self._run_now(payload["skill"], payload.get("args", {}))

    @staticmethod
    def _summarize(name: str, args: dict) -> str:
        if not args:
            return ""
        parts = ", ".join(f"{k}=`{str(v)[:80]}`" for k, v in args.items())
        return f" — {parts}"


_registry = SkillRegistry()


def get_registry() -> SkillRegistry:
    return _registry
