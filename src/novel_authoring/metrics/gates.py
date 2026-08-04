from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.metrics.formulas import character_fit, style_fit


class HardGateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canon_conflicts: list[str] = Field(default_factory=list)
    timeline_conflicts: list[str] = Field(default_factory=list)
    knowledge_violations: list[str] = Field(default_factory=list)
    missing_causal_sources: list[str] = Field(default_factory=list)
    payoff_cooldown_violations: list[str] = Field(default_factory=list)
    capability_violations: list[str] = Field(default_factory=list)
    author_constraint_violations: list[str] = Field(default_factory=list)
    style_boundary_violations: list[str] = Field(default_factory=list)
    character_bottom_line_violation: bool = False
    character_fit_inputs: dict[str, float]
    style_fit_inputs: dict[str, float]


class GateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    hard_failures: list[str]
    character_fit: float
    style_fit: float
    requires_character_bridge: bool
    style_review_required: bool


def evaluate_hard_gates(
    gate_input: HardGateInput, metrics_config: dict[str, object]
) -> GateReport:
    failures = [
        *gate_input.canon_conflicts,
        *gate_input.timeline_conflicts,
        *gate_input.knowledge_violations,
        *gate_input.missing_causal_sources,
        *gate_input.payoff_cooldown_violations,
        *gate_input.capability_violations,
        *gate_input.author_constraint_violations,
        *gate_input.style_boundary_violations,
    ]
    character_config = metrics_config["character_fit"]
    style_config = metrics_config["style_fit"]
    if not isinstance(character_config, dict) or not isinstance(style_config, dict):
        raise ValueError("Character/Style 配置无效")
    character_score = character_fit(gate_input.character_fit_inputs, character_config)
    style_score = style_fit(gate_input.style_fit_inputs, style_config)
    requires_bridge = character_score < float(character_config["minimum"])
    if gate_input.character_bottom_line_violation:
        failures.append("人物底线冲突且无桥梁")
    return GateReport(
        passed=not failures and not requires_bridge,
        hard_failures=failures,
        character_fit=character_score,
        style_fit=style_score,
        requires_character_bridge=requires_bridge,
        style_review_required=bool(gate_input.style_boundary_violations),
    )
