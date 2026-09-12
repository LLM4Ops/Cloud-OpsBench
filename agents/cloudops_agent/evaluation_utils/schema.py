from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ToolCall:
    """A normalized tool call."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass(frozen=True)
class TrajectoryStep:
    """One trajectory action/observation pair."""

    tool_call: ToolCall
    observation: Any


@dataclass(frozen=True)
class EvidencePattern:
    """A single observation matcher.

    Supported kinds:
    - literal: case-insensitive substring by default
    - regex: Python regular expression, DOTALL by default
    - json_path: simple dotted path over JSON-like objects
    - yaml_path: best-effort path matcher over YAML-ish text
    - code_snippet: whitespace-normalized snippet matcher
    """

    kind: str
    value: Any
    flags: Sequence[str] = field(default_factory=tuple)
    path: Optional[str] = None
    equals: Any = None
    contains: Any = None
    manual_review_required: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidencePattern":
        return cls(
            kind=str(data["kind"]),
            value=data.get("value"),
            flags=tuple(data.get("flags", ())),
            path=data.get("path"),
            equals=data.get("equals"),
            contains=data.get("contains"),
            manual_review_required=bool(data.get("manual_review_required", False)),
        )


@dataclass(frozen=True)
class AdmissibleToolUse:
    """One acceptable way to establish a milestone."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    evidence_patterns: Sequence[EvidencePattern] = field(default_factory=tuple)
    note: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AdmissibleToolUse":
        return cls(
            tool_name=str(data["tool_name"]),
            arguments=dict(data.get("arguments", {})),
            evidence_patterns=tuple(
                EvidencePattern.from_dict(item)
                for item in data.get("evidence_patterns", ())
            ),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class AdmissibleEvidenceGroup:
    """A compound way to establish a milestone with multiple observations."""

    tool_uses: Sequence[AdmissibleToolUse] = field(default_factory=tuple)
    note: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AdmissibleEvidenceGroup":
        return cls(
            tool_uses=tuple(
                AdmissibleToolUse.from_dict(item)
                for item in data.get("tool_uses", ())
            ),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class Milestone:
    """A diagnostic fact, not a command."""

    milestone_id: str
    description: str
    role: str
    name: str = ""
    admissible_tool_uses: Sequence[AdmissibleToolUse] = field(default_factory=tuple)
    admissible_evidence_groups: Sequence[AdmissibleEvidenceGroup] = field(default_factory=tuple)
    manual_review_required: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Milestone":
        return cls(
            milestone_id=str(data["id"]),
            description=str(data["description"]),
            role=str(data.get("role", "")),
            name=str(data.get("name", "")),
            admissible_tool_uses=tuple(
                AdmissibleToolUse.from_dict(item)
                for item in data.get("admissible_tool_uses", ())
            ),
            admissible_evidence_groups=tuple(
                AdmissibleEvidenceGroup.from_dict(item)
                for item in data.get("admissible_evidence_groups", ())
            ),
            manual_review_required=bool(data.get("manual_review_required", False)),
        )


@dataclass(frozen=True)
class CaseAnnotation:
    """Ground-truth diagnostic evidence graph for one case."""

    case_id: str
    namespace: str
    query: str
    result: Mapping[str, Any]
    milestones: Sequence[Milestone]
    dependency_edges: Sequence[Tuple[str, str]]
    completion_formula: Mapping[str, Any] | str | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CaseAnnotation":
        dependency_edges = []
        for edge in data.get("dependency_edges", ()):
            if isinstance(edge, Mapping):
                dependency_edges.append((str(edge["from"]), str(edge["to"])))
            else:
                dependency_edges.append((str(edge[0]), str(edge[1])))
        return cls(
            case_id=str(data["case_id"]),
            namespace=str(data.get("namespace", "")),
            query=str(data.get("query", "")),
            result=dict(data.get("result", {})),
            milestones=tuple(Milestone.from_dict(item) for item in data["milestones"]),
            dependency_edges=tuple(dependency_edges),
            completion_formula=data.get("completion_formula"),
            notes=str(data.get("notes", "")),
        )

    @property
    def milestone_ids(self) -> List[str]:
        return [milestone.milestone_id for milestone in self.milestones]
