import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings
from app.governance.policy import DEFAULT_POLICIES, GovernancePolicy, PolicyLevel
from app.utils import logger

_GOVDIR = lambda: settings.get_data_path() / "governance"
_POLICIES_FILE = lambda: _GOVDIR() / "policies.json"
_AUDIT_FILE = lambda: _GOVDIR() / "audit.jsonl"
_PENDING_FILE = lambda: _GOVDIR() / "pending.json"


class GovernanceManager:
    def __init__(self):
        _GOVDIR().mkdir(parents=True, exist_ok=True)
        self.policies: dict[str, GovernancePolicy] = dict(DEFAULT_POLICIES)
        self._pending: dict[str, dict] = {}
        self._load()

    def _load(self):
        pf = _POLICIES_FILE()
        if pf.exists():
            try:
                raw = json.loads(pf.read_text())
                for name, data in raw.items():
                    self.policies[name] = GovernancePolicy.from_dict(data)
            except Exception as e:
                logger.warning(f"Governance: failed to load policies: {e}")
        pend = _PENDING_FILE()
        if pend.exists():
            try:
                self._pending = json.loads(pend.read_text())
            except Exception:
                self._pending = {}

    def _save_policies(self):
        _POLICIES_FILE().write_text(
            json.dumps({k: v.to_dict() for k, v in self.policies.items()}, indent=2)
        )

    def _save_pending(self):
        _PENDING_FILE().write_text(json.dumps(self._pending, indent=2))

    def check(self, resource_type: str, action: str, context: dict = None) -> dict:
        """Return {allowed, level, reason, request_id?}."""
        context = context or {}
        matched: Optional[GovernancePolicy] = None
        for policy in self.policies.values():
            if resource_type in policy.applies_to:
                matched = policy
                break

        if matched is None:
            return {"allowed": True, "level": "allow", "reason": "No policy matched — default allow"}

        if matched.level == PolicyLevel.ALLOW:
            self.log_action(resource_type, action, "allowed", context)
            return {"allowed": True, "level": "allow", "reason": f"Policy '{matched.name}' allows"}

        if matched.level == PolicyLevel.BLOCK:
            self.log_action(resource_type, action, "blocked", context)
            return {"allowed": False, "level": "block", "reason": f"Policy '{matched.name}' blocks this action"}

        # REQUIRE_APPROVAL — queue it
        request_id = str(uuid.uuid4())[:8]
        self._pending[request_id] = {
            "id": request_id,
            "resource_type": resource_type,
            "action": action,
            "policy": matched.name,
            "context": context,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_pending()
        self.log_action(resource_type, action, "pending_approval", context)
        return {
            "allowed": False,
            "level": "require_approval",
            "reason": f"Policy '{matched.name}' requires approval",
            "request_id": request_id,
        }

    def gate_tool(self, skill: str, args: dict) -> dict:
        """Gate a high-risk skill call using the 'high_risk_tool' policy.
        Returns {allowed, level, request_id?}. On REQUIRE_APPROVAL the call is
        queued with its skill+args so it can be executed on approval."""
        policy = self.policies.get("high_risk_tool")
        level = policy.level if policy else PolicyLevel.REQUIRE_APPROVAL
        action = f"{skill}({', '.join(f'{k}={str(v)[:60]}' for k, v in (args or {}).items())})"

        if level == PolicyLevel.ALLOW:
            self.log_action("tool", action, "allowed", {"skill": skill})
            return {"allowed": True, "level": "allow"}
        if level == PolicyLevel.BLOCK:
            self.log_action("tool", action, "blocked", {"skill": skill})
            return {"allowed": False, "level": "block"}

        request_id = str(uuid.uuid4())[:8]
        self._pending[request_id] = {
            "id": request_id,
            "resource_type": "tool",
            "skill": skill,
            "args": args or {},
            "action": action,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_pending()
        self.log_action("tool", action, "pending_approval", {"skill": skill})
        return {"allowed": False, "level": "require_approval", "request_id": request_id}

    def take_approved(self, request_id: str) -> Optional[dict]:
        """If the request is approved, consume it and return {skill, args}."""
        p = self._pending.get(request_id)
        if not p or p.get("status") != "approved":
            return None
        del self._pending[request_id]
        self._save_pending()
        return {"skill": p.get("skill"), "args": p.get("args", {})}

    def approve(self, request_id: str) -> bool:
        if request_id not in self._pending:
            return False
        self._pending[request_id]["status"] = "approved"
        self._pending[request_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
        self._save_pending()
        logger.info(f"Governance: approved request {request_id}")
        return True

    def deny(self, request_id: str) -> bool:
        if request_id not in self._pending:
            return False
        self._pending[request_id]["status"] = "denied"
        self._pending[request_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
        self._save_pending()
        logger.info(f"Governance: denied request {request_id}")
        return True

    def get_pending(self) -> list:
        return [v for v in self._pending.values() if v["status"] == "pending"]

    def update_policy(self, name: str, level: PolicyLevel) -> bool:
        if name not in self.policies:
            return False
        self.policies[name].level = level
        self._save_policies()
        logger.info(f"Governance: policy '{name}' set to {level.value}")
        return True

    def log_action(self, resource_type: str, action: str, outcome: str, context: dict):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "resource_type": resource_type,
            "action": action,
            "outcome": outcome,
            "context": {k: str(v)[:200] for k, v in (context or {}).items()},
        }
        with open(_AUDIT_FILE(), "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_audit(self, limit: int = 100) -> list:
        af = _AUDIT_FILE()
        if not af.exists():
            return []
        lines = af.read_text().strip().splitlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return list(reversed(entries))


_manager: Optional[GovernanceManager] = None


def get_governance_manager() -> GovernanceManager:
    global _manager
    if _manager is None:
        _manager = GovernanceManager()
    return _manager
