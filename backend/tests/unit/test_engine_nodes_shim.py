"""M9.1: market_entry node shims expose engine factories."""

from app.agents._engine.nodes.audit import build_audit_node as eng_audit
from app.agents._engine.nodes.framing import build_framing_node as eng_framing
from app.agents._engine.nodes.reviewer import make_reviewer_node as eng_reviewer
from app.agents._engine.nodes.stage import make_stage_node as eng_stage
from app.agents._engine.nodes.synthesis import build_synthesis_node as eng_synthesis
from app.agents.market_entry.nodes.audit import build_audit_node as me_audit
from app.agents.market_entry.nodes.framing import build_framing_node as me_framing
from app.agents.market_entry.nodes.reviewer import make_reviewer_node as me_reviewer
from app.agents.market_entry.nodes.stage import make_stage_node as me_stage
from app.agents.market_entry.nodes.synthesis import build_synthesis_node as me_synthesis


def test_shims_delegate() -> None:
    assert me_framing is eng_framing
    assert me_stage is eng_stage
    assert me_reviewer is eng_reviewer
    assert me_synthesis is eng_synthesis
    assert me_audit is eng_audit
