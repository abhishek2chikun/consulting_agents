"""M9.1: ConsultingProfile - profile-driven configuration for the shared engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources

from app.agents._engine.skills import load_skill


@dataclass(frozen=True)
class WorkerSpec:
    slug: str
    prompt_file: str
    required_skills: tuple[str, ...] = ()


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
    required_skills: tuple[str, ...] = ()
    workers: tuple[WorkerSpec, ...] = ()
    max_retries: int | None = None


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
    framing_skills: tuple[str, ...] = ()
    synthesis_skills: tuple[str, ...] = ()
    audit_skills: tuple[str, ...] = ()
    reviewer_skills_per_stage: dict[str, tuple[str, ...]] = field(default_factory=dict)
    reviewer_prompt_for_stage: dict[str, str] = field(default_factory=dict)

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

    def load_worker_prompt(self, stage_slug: str, worker_slug: str) -> str:
        for stage in self.stages:
            if stage.slug != stage_slug:
                continue
            for worker in stage.workers:
                if worker.slug == worker_slug:
                    return self._read(self.prompts_package, worker.prompt_file)
            raise KeyError(f"Unknown worker for stage {stage_slug!r}: {worker_slug!r}")
        raise KeyError(f"Unknown stage for profile {self.slug!r}: {stage_slug!r}")

    def validate(self) -> ConsultingProfile:
        """Read every referenced prompt; raises FileNotFoundError if any missing."""
        self.load_prompt("framing")
        self.load_prompt("synthesis")
        self.load_prompt("audit")
        self.load_prompt("reviewer")
        stage_slugs: set[str] = set()
        for stage in self.stages:
            if stage.slug in stage_slugs:
                raise ValueError(f"Duplicate stage slug in profile {self.slug!r}: {stage.slug!r}")
            stage_slugs.add(stage.slug)
        for stage_slug in self.reviewer_prompt_for_stage:
            if stage_slug not in stage_slugs:
                raise ValueError(
                    f"Unknown reviewer prompt stage for profile {self.slug!r}: {stage_slug!r}"
                )
        for stage_slug in self.reviewer_skills_per_stage:
            if stage_slug not in stage_slugs:
                raise ValueError(
                    f"Unknown reviewer skills stage for profile {self.slug!r}: {stage_slug!r}"
                )
        for skill_slug in self.framing_skills:
            load_skill(skill_slug)
        for skill_slug in self.synthesis_skills:
            load_skill(skill_slug)
        for skill_slug in self.audit_skills:
            load_skill(skill_slug)
        for skill_slugs in self.reviewer_skills_per_stage.values():
            for skill_slug in skill_slugs:
                load_skill(skill_slug)
        for prompt_file in self.reviewer_prompt_for_stage.values():
            self._read(self.reviewer_prompt_package, prompt_file)
        for stage in self.stages:
            self.load_prompt(stage.slug)
            for skill_slug in stage.required_skills:
                load_skill(skill_slug)
            worker_slugs: set[str] = set()
            for worker in stage.workers:
                if worker.slug in worker_slugs:
                    raise ValueError(
                        f"Duplicate worker slug in stage {stage.slug!r}: {worker.slug!r}"
                    )
                worker_slugs.add(worker.slug)
                self.load_worker_prompt(stage.slug, worker.slug)
                for skill_slug in worker.required_skills:
                    load_skill(skill_slug)
        return self

    @staticmethod
    def _read(package: str, filename: str) -> str:
        return resources.files(package).joinpath(filename).read_text(encoding="utf-8")
