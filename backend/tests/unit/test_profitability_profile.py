"""M9.2: profitability profile registered and prompts load."""

import app.agents.profitability  # noqa: F401  # import triggers registration
from app.agents._engine.registry import PROFILE_REGISTRY


def test_registered() -> None:
    assert "profitability" in PROFILE_REGISTRY


def test_five_stages() -> None:
    p = PROFILE_REGISTRY["profitability"]
    assert len(p.stages) == 5
    assert [s.slug for s in p.stages] == [
        "stage1_revenue",
        "stage2_cost",
        "stage3_margin",
        "stage4_competitor",
        "stage5_levers",
    ]
    assert [s.next_stage_node for s in p.stages] == [
        "stage2_cost",
        "stage3_margin",
        "stage4_competitor",
        "stage5_levers",
        "synthesis",
    ]


def test_all_prompts_load() -> None:
    p = PROFILE_REGISTRY["profitability"]
    for role in ("framing", "synthesis", "audit", "reviewer"):
        assert len(p.load_prompt(role)) > 50
    for stage in p.stages:
        assert len(p.load_prompt(stage.slug)) > 50
