"""M9.1: ConsultingProfile - profile-driven configuration for the shared engine."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class ProfileStage:
    """One stage of a consulting pipeline.

    `node_name` is the LangGraph node label.
    `next_stage_node` is the node to route to on reviewer 'continue'.
        Use 'synthesis' for the final stage.
    `prompt_file` is the filename inside the profile's prompts_package.
    """

    slug: str
    node_name: str
    next_stage_node: str
    prompt_file: str


@dataclass(frozen=True)
class ConsultingProfile:
    """A consulting type's full configuration.

    Stage prompts live in ``prompts_package``. Reviewer prompt may live in a
    separate package (default: same as stage prompts) so types can share a
    common reviewer.
    """

    slug: str
    display_name: str
    prompts_package: str
    framing_prompt: str
    stages: tuple[ProfileStage, ...]
    reviewer_prompt_package: str
    reviewer_prompt: str
    synthesis_prompt: str
    audit_prompt: str

    def load_prompt(self, role: str) -> str:
        """Load a prompt by role: framing|synthesis|audit|reviewer|<stage_slug>."""
        if role == "framing":
            return self._read(self.prompts_package, self.framing_prompt)
        if role == "synthesis":
            return self._read(self.prompts_package, self.synthesis_prompt)
        if role == "audit":
            return self._read(self.prompts_package, self.audit_prompt)
        if role == "reviewer":
            return self._read(self.reviewer_prompt_package, self.reviewer_prompt)
        for stage in self.stages:
            if stage.slug == role or stage.node_name == role:
                return self._read(self.prompts_package, stage.prompt_file)
        raise KeyError(f"Unknown prompt role for profile {self.slug!r}: {role!r}")

    def validate(self) -> ConsultingProfile:
        """Read every referenced prompt; raises FileNotFoundError if any missing."""
        self.load_prompt("framing")
        self.load_prompt("synthesis")
        self.load_prompt("audit")
        self.load_prompt("reviewer")
        for stage in self.stages:
            self.load_prompt(stage.slug)
        return self

    @staticmethod
    def _read(package: str, filename: str) -> str:
        try:
            return resources.files(package).joinpath(filename).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - unwrap importlib edge cases
            raise FileNotFoundError(f"{package}/{filename}: {exc}") from exc
