"""Back-compat shim: stage node moved to app.agents._engine.nodes.stage."""

from app.agents._engine.nodes.stage import (
    ArtifactFile,
    EvidenceCitation,
    StageOutput,
    make_stage_node,
)

__all__ = ["ArtifactFile", "EvidenceCitation", "StageOutput", "make_stage_node"]
