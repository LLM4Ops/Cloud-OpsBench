from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Sequence

from .matcher import pattern_matches, tool_use_matches
from .schema import CaseAnnotation, Milestone, TrajectoryStep


@dataclass(frozen=True)
class MilestoneMatch:
    milestone_id: str
    step_index: int
    tool_name: str
    admissible_index: int
    evidence_group_index: int | None = None
    manual_review_required: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    established: Mapping[str, MilestoneMatch]
    ordered: Mapping[str, MilestoneMatch]
    missing: Sequence[str]
    satisfied_edges: Sequence[tuple[str, str]]
    unsatisfied_edges: Sequence[tuple[str, str]]
    process_complete: bool
    milestone_count: int
    milestone_coverage_score: float
    evidence_order_coverage_score: float
    total_tool_calls: int
    evidence_tool_count: int
    manual_review_milestones: Sequence[str] = field(default_factory=tuple)

    @property
    def established_ids(self) -> List[str]:
        return list(self.established.keys())

    @property
    def ordered_ids(self) -> List[str]:
        return list(self.ordered.keys())

    @property
    def milestone_coverage(self) -> float:
        return self.milestone_coverage_score

    @property
    def evidence_order_coverage(self) -> float:
        return self.evidence_order_coverage_score

    @property
    def evidence_efficiency(self) -> float:
        if self.total_tool_calls == 0:
            return 0.0
        return self.evidence_tool_count / self.total_tool_calls


def evaluate_trajectory(
    annotation: CaseAnnotation, trajectory: Iterable[TrajectoryStep]
) -> EvaluationResult:
    steps = list(trajectory)
    hits_by_milestone: Dict[str, List[MilestoneMatch]] = {}
    established: Dict[str, MilestoneMatch] = {}

    for milestone in annotation.milestones:
        matches = _match_milestone_hits(milestone, steps)
        if matches:
            hits_by_milestone[milestone.milestone_id] = matches
            established[milestone.milestone_id] = matches[0]

    ordered = _order_grounded_matches(annotation, hits_by_milestone, len(steps))
    evidence_tool_indices = {
        match.step_index
        for matches in hits_by_milestone.values()
        for match in matches
    }

    established_ids = set(established)
    missing = [item for item in annotation.milestone_ids if item not in established_ids]
    satisfied_edges = []
    unsatisfied_edges = []
    for edge in annotation.dependency_edges:
        if edge[0] in established_ids and edge[1] in established_ids:
            satisfied_edges.append(edge)
        elif edge[1] in established_ids:
            unsatisfied_edges.append(edge)
        else:
            continue

    manual_review = sorted(
        milestone_id
        for milestone_id, match in established.items()
        if match.manual_review_required
    )
    if annotation.completion_formula is None:
        process_complete = not missing and not unsatisfied_edges
    else:
        process_complete = _formula_satisfied(
            annotation.completion_formula, established_ids
        ) and not unsatisfied_edges
    coverage_formula = annotation.completion_formula or annotation.milestone_ids
    return EvaluationResult(
        case_id=annotation.case_id,
        established=established,
        ordered=ordered,
        missing=tuple(missing),
        satisfied_edges=tuple(satisfied_edges),
        unsatisfied_edges=tuple(unsatisfied_edges),
        process_complete=process_complete,
        milestone_count=len(annotation.milestones),
        milestone_coverage_score=_formula_score(coverage_formula, established_ids),
        evidence_order_coverage_score=_formula_score(
            coverage_formula, set(ordered)
        ),
        total_tool_calls=len(steps),
        evidence_tool_count=len(evidence_tool_indices),
        manual_review_milestones=tuple(manual_review),
    )


def _match_milestone(
    milestone: Milestone, steps: Sequence[TrajectoryStep]
) -> MilestoneMatch | None:
    matches = _match_milestone_hits(milestone, steps)
    return matches[0] if matches else None


def _match_milestone_hits(
    milestone: Milestone, steps: Sequence[TrajectoryStep]
) -> List[MilestoneMatch]:
    matches: List[MilestoneMatch] = []
    matches.extend(_match_single_tool_use_hits(milestone, steps))
    matches.extend(_match_evidence_group_hits(milestone, steps))
    return sorted(matches, key=lambda item: (item.step_index, item.admissible_index))


def _match_evidence_group_hits(
    milestone: Milestone, steps: Sequence[TrajectoryStep]
) -> List[MilestoneMatch]:
    matches: List[MilestoneMatch] = []
    for group_index, group in enumerate(milestone.admissible_evidence_groups):
        component_hit_by_step: Dict[int, List[tuple[int, str]]] = {}
        for component_index, component in enumerate(group.tool_uses):
            for step_index, step in enumerate(steps):
                if _admissible_matches_step(component, step):
                    component_hit_by_step.setdefault(step_index, []).append(
                        (component_index, step.tool_call.tool_name)
                    )

        seen_components: set[int] = set()
        seen_tool_names: Dict[int, str] = {}
        for step_index in range(len(steps)):
            step_component_hits = component_hit_by_step.get(step_index, [])
            if not step_component_hits:
                continue
            for component_index, tool_name in step_component_hits:
                seen_components.add(component_index)
                seen_tool_names.setdefault(component_index, tool_name)
            if len(seen_components) != len(group.tool_uses):
                continue
            manual_review_required = milestone.manual_review_required or any(
                pattern.manual_review_required
                for component in group.tool_uses
                for pattern in component.evidence_patterns
            )
            matches.append(
                MilestoneMatch(
                    milestone_id=milestone.milestone_id,
                    step_index=step_index,
                    tool_name="+".join(
                        seen_tool_names[index]
                        for index in sorted(seen_tool_names)
                    ),
                    admissible_index=-1,
                    evidence_group_index=group_index,
                    manual_review_required=manual_review_required,
                )
            )
    return matches


def _match_single_tool_use(
    milestone: Milestone, steps: Sequence[TrajectoryStep]
) -> MilestoneMatch | None:
    matches = _match_single_tool_use_hits(milestone, steps)
    return matches[0] if matches else None


def _match_single_tool_use_hits(
    milestone: Milestone, steps: Sequence[TrajectoryStep]
) -> List[MilestoneMatch]:
    matches: List[MilestoneMatch] = []
    for step_index, step in enumerate(steps):
        for admissible_index, admissible in enumerate(milestone.admissible_tool_uses):
            if _admissible_matches_step(admissible, step):
                manual_review_required = milestone.manual_review_required or any(
                    pattern.manual_review_required
                    for pattern in admissible.evidence_patterns
                )
                matches.append(
                    MilestoneMatch(
                        milestone_id=milestone.milestone_id,
                        step_index=step_index,
                        tool_name=step.tool_call.tool_name,
                        admissible_index=admissible_index,
                        manual_review_required=manual_review_required,
                    )
                )
    return matches


def _admissible_matches_step(admissible, step: TrajectoryStep) -> bool:
    if not tool_use_matches(step.tool_call, admissible):
        return False
    return all(
        pattern_matches(pattern, step.observation)
        for pattern in admissible.evidence_patterns
    )


def _order_grounded_matches(
    annotation: CaseAnnotation,
    hits_by_milestone: Mapping[str, Sequence[MilestoneMatch]],
    step_count: int,
) -> Dict[str, MilestoneMatch]:
    prerequisites: Dict[str, set[str]] = {
        milestone_id: set() for milestone_id in annotation.milestone_ids
    }
    for source, target in annotation.dependency_edges:
        prerequisites.setdefault(target, set()).add(source)

    hits_by_step: Dict[int, List[MilestoneMatch]] = {}
    for matches in hits_by_milestone.values():
        for match in matches:
            hits_by_step.setdefault(match.step_index, []).append(match)

    ordered: Dict[str, MilestoneMatch] = {}
    for step_index in range(step_count):
        candidates = [
            match
            for match in hits_by_step.get(step_index, [])
            if match.milestone_id not in ordered
        ]
        changed = True
        while changed:
            changed = False
            remaining = []
            for match in candidates:
                if prerequisites.get(match.milestone_id, set()).issubset(ordered):
                    ordered[match.milestone_id] = match
                    changed = True
                else:
                    remaining.append(match)
            candidates = remaining
    return ordered


def _formula_satisfied(formula, established_ids: set[str]) -> bool:
    if isinstance(formula, str):
        return formula in established_ids
    if isinstance(formula, list):
        return all(_formula_satisfied(item, established_ids) for item in formula)
    if not isinstance(formula, Mapping):
        return False
    if "all" in formula:
        return all(_formula_satisfied(item, established_ids) for item in formula["all"])
    if "any" in formula:
        return any(_formula_satisfied(item, established_ids) for item in formula["any"])
    if "milestone" in formula:
        return str(formula["milestone"]) in established_ids
    return False


def _formula_score(formula, milestone_ids: set[str]) -> float:
    if isinstance(formula, str):
        return 1.0 if formula in milestone_ids else 0.0
    if isinstance(formula, list):
        if not formula:
            return 0.0
        return sum(_formula_score(item, milestone_ids) for item in formula) / len(formula)
    if not isinstance(formula, Mapping):
        return 0.0
    if "all" in formula:
        children = formula["all"]
        if not children:
            return 0.0
        return sum(_formula_score(item, milestone_ids) for item in children) / len(children)
    if "any" in formula:
        children = formula["any"]
        if not children:
            return 0.0
        return max(_formula_score(item, milestone_ids) for item in children)
    if "milestone" in formula:
        return 1.0 if str(formula["milestone"]) in milestone_ids else 0.0
    return 0.0
