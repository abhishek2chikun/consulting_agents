from __future__ import annotations

from app.agents._engine.nodes.audit import _get_artifact_by_path
from app.agents._engine.paths import normalize_artifact_path


def test_normalize_artifact_path_expands_stage_3_risk_risk_path() -> None:
    assert normalize_artifact_path("stage_3_risk/risk.md") == {
        "stage_3_risk/risk.md",
        "stage3_risk/risk.md",
        "stage_3_risk/findings.md",
        "stage3_risk/findings.md",
    }


def test_normalize_artifact_path_expands_stage3_risk_findings_path() -> None:
    assert normalize_artifact_path("stage3_risk/findings.md") == {
        "stage3_risk/findings.md",
        "stage_3_risk/findings.md",
        "stage3_risk/risk.md",
        "stage_3_risk/risk.md",
    }


def test_normalize_artifact_path_leaves_unknown_path_unchanged() -> None:
    assert normalize_artifact_path("stage1_foundation/summary.md") == {
        "stage1_foundation/summary.md"
    }


def test_artifact_lookup_reads_alias_and_preserves_original_path() -> None:
    path, content = _get_artifact_by_path(
        {"stage3_risk/findings.md": "risk content"}, "stage_3_risk/risk.md"
    )

    assert path == "stage3_risk/findings.md"
    assert content == "risk content"
