from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List

from .matcher import observation_to_text, pattern_matches, tool_use_matches
from .schema import CaseAnnotation, TrajectoryStep


def enumerate_q_candidates(
    annotation: CaseAnnotation,
    tool_cache_steps: Iterable[TrajectoryStep],
    *,
    strict: bool = False,
    preview_chars: int = 240,
) -> Dict[str, Any]:
    """Enumerate tool-cache calls that can establish each annotated milestone.

    In strict mode, a cache step must match the annotated tool name/arguments and
    evidence patterns. In evidence-only mode, every cache step is scanned against
    each admissible evidence-pattern group, and the output marks whether it also
    matches the currently annotated tool use.
    """

    steps = list(tool_cache_steps)
    milestones: List[Dict[str, Any]] = []
    for milestone in annotation.milestones:
        groups: List[Dict[str, Any]] = []
        for admissible_index, admissible in enumerate(milestone.admissible_tool_uses):
            matches: List[Dict[str, Any]] = []
            if not admissible.evidence_patterns:
                for step_index, step in enumerate(steps):
                    strict_tool_match = tool_use_matches(step.tool_call, admissible)
                    if not strict_tool_match:
                        continue
                    matches.append(
                        _candidate_to_dict(
                            step,
                            step_index=step_index,
                            strict_tool_use_match=strict_tool_match,
                            preview_chars=preview_chars,
                        )
                    )
            else:
                for step_index, step in enumerate(steps):
                    strict_tool_match = tool_use_matches(step.tool_call, admissible)
                    if strict and not strict_tool_match:
                        continue
                    if not all(
                        pattern_matches(pattern, step.observation)
                        for pattern in admissible.evidence_patterns
                    ):
                        continue
                    matches.append(
                        _candidate_to_dict(
                            step,
                            step_index=step_index,
                            strict_tool_use_match=strict_tool_match,
                            preview_chars=preview_chars,
                        )
                    )

            groups.append(
                {
                    "admissible_index": admissible_index,
                    "annotated_tool_name": admissible.tool_name,
                    "annotated_arguments": dict(admissible.arguments),
                    "evidence_pattern_count": len(admissible.evidence_patterns),
                    "matches": matches,
                }
            )

        evidence_groups: List[Dict[str, Any]] = []
        for group_index, evidence_group in enumerate(milestone.admissible_evidence_groups):
            components: List[Dict[str, Any]] = []
            for component_index, admissible in enumerate(evidence_group.tool_uses):
                matches = []
                if not admissible.evidence_patterns:
                    for step_index, step in enumerate(steps):
                        strict_tool_match = tool_use_matches(step.tool_call, admissible)
                        if not strict_tool_match:
                            continue
                        matches.append(
                            _candidate_to_dict(
                                step,
                                step_index=step_index,
                                strict_tool_use_match=strict_tool_match,
                                preview_chars=preview_chars,
                            )
                        )
                else:
                    for step_index, step in enumerate(steps):
                        strict_tool_match = tool_use_matches(step.tool_call, admissible)
                        if strict and not strict_tool_match:
                            continue
                        if not all(
                            pattern_matches(pattern, step.observation)
                            for pattern in admissible.evidence_patterns
                        ):
                            continue
                        matches.append(
                            _candidate_to_dict(
                                step,
                                step_index=step_index,
                                strict_tool_use_match=strict_tool_match,
                                preview_chars=preview_chars,
                            )
                        )
                components.append(
                    {
                        "component_index": component_index,
                        "annotated_tool_name": admissible.tool_name,
                        "annotated_arguments": dict(admissible.arguments),
                        "evidence_pattern_count": len(admissible.evidence_patterns),
                        "matches": matches,
                    }
                )
            evidence_groups.append(
                {
                    "evidence_group_index": group_index,
                    "note": evidence_group.note,
                    "components": components,
                }
            )

        milestones.append(
            {
                "id": milestone.milestone_id,
                "description": milestone.description,
                "role": milestone.role,
                "candidate_groups": groups,
                "compound_candidate_groups": evidence_groups,
            }
        )

    return {
        "case_id": annotation.case_id,
        "mode": "strict" if strict else "evidence-only",
        "milestones": milestones,
    }


def _candidate_to_dict(
    step: TrajectoryStep,
    *,
    step_index: int,
    strict_tool_use_match: bool,
    preview_chars: int,
) -> Dict[str, Any]:
    text = observation_to_text(step.observation)
    return {
        "step_index": step_index,
        "cache_key": step.tool_call.raw,
        "tool_name": step.tool_call.tool_name,
        "arguments": dict(step.tool_call.arguments),
        "strict_tool_use_match": strict_tool_use_match,
        "observation_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "observation_chars": len(text),
        "preview": _preview(text, preview_chars),
    }


def _preview(text: str, preview_chars: int) -> str:
    one_line = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return one_line[:preview_chars]
