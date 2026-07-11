"""Supervised gate: high-risk skills need approval; low-risk run freely."""
import re
import pytest

from app.skills.registry import get_registry, HIGH_RISK_SKILLS
from app.governance.manager import get_governance_manager
from app.governance.policy import PolicyLevel


@pytest.mark.asyncio
async def test_high_risk_skill_is_gated_then_runs_on_approval():
    reg, gm = get_registry(), get_governance_manager()
    out = await reg.run("run_shell", {"command": "echo hi"})
    assert "Approval needed" in out                      # gated, not executed
    rid = re.search(r"/approve (\w+)", out).group(1)
    assert gm.approve(rid)
    result = await reg.execute_approved(rid)
    assert "hi" in str(result)                            # runs after approval
    assert gm.take_approved(rid) is None                  # consumed, can't replay


@pytest.mark.asyncio
async def test_denied_action_never_runs():
    reg, gm = get_registry(), get_governance_manager()
    out = await reg.run("clean_junk", {})
    rid = re.search(r"/approve (\w+)", out).group(1)
    assert gm.deny(rid)
    assert gm.take_approved(rid) is None                  # denied => nothing to run


@pytest.mark.asyncio
async def test_low_risk_skill_runs_without_approval():
    result = await get_registry().run("calculator", {"expression": "2+2"})
    assert "4" in str(result)


@pytest.mark.asyncio
async def test_policy_allow_disables_the_gate():
    gm = get_governance_manager()
    gm.update_policy("high_risk_tool", PolicyLevel.ALLOW)
    try:
        # ALLOW => decision.allowed True, so it executes instead of asking
        out = await get_registry().run("run_python", {"code": "print(6*7)"})
        assert "Approval needed" not in str(out)
        assert "42" in str(out)
    finally:
        gm.update_policy("high_risk_tool", PolicyLevel.REQUIRE_APPROVAL)


def test_high_risk_set_is_sane():
    assert {"run_shell", "run_python", "clean_junk"} <= HIGH_RISK_SKILLS
