from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


# Legacy atom-card format. It remains readable for systems that have not yet
# been migrated to the self-contained Diagnostic Graph Skill schema.
ATOM_KEYS = {
    "atom_id",
    "name",
    "intent",
    "core_action",
    "optional_actions",
    "expected_evidence",
}
DAG_KEYS = {
    "system",
    "symptom_id",
    "name",
    "description",
    "surface_signals",
    "entry_atoms",
    "nodes",
}
NODE_KEYS = {"atom_file", "next"}

# Canonical self-contained Diagnostic Graph Skill format used by H0 Boutique.
SKILL_KEYS = {
    "schema_version",
    "system",
    "symptom_id",
    "description",
    "signals",
    "entry",
    "nodes",
}
SKILL_NODE_KEYS = {"goal", "actions", "evidence", "next"}
SKILL_ACTION_KEYS = {"tool", "args"}


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return value


def _string_list(
    value: Any,
    field: str,
    path: Path,
    *,
    allow_empty: bool = True,
) -> List[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a list of non-empty strings: {path}")
    result = [item.strip() for item in value]
    if not allow_empty and not result:
        raise ValueError(f"{field} must not be empty: {path}")
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicates: {path}")
    return result


@dataclass(frozen=True)
class AtomSkill:
    atom_id: str
    name: str
    intent: str
    core_action: str
    optional_actions: tuple[str, ...]
    expected_evidence: tuple[str, ...]

    def to_prompt_dict(self) -> Dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "name": self.name,
            "intent": self.intent,
            "core_action": self.core_action,
            "optional_actions": list(self.optional_actions),
            "expected_evidence": list(self.expected_evidence),
        }


@dataclass(frozen=True)
class DagNode:
    atom_id: str
    next_atoms: tuple[str, ...]


@dataclass(frozen=True)
class SymptomDag:
    system: str
    symptom_id: str
    name: str
    description: str
    surface_signals: tuple[str, ...]
    entry_atoms: tuple[str, ...]
    nodes: Dict[str, DagNode]

    def catalog_item(self) -> Dict[str, Any]:
        return {
            "symptom_id": self.symptom_id,
            "name": self.name,
            "description": self.description,
            "surface_signals": list(self.surface_signals),
        }


class SymptomDagRegistry:
    """Load complete symptom skills without matching them to observations."""

    def __init__(
        self,
        dags: Dict[str, SymptomDag],
        prompt_skills: Dict[str, Dict[str, Any]],
    ):
        self.dags = dags
        self._prompt_skills = prompt_skills

    @classmethod
    def load(
        cls,
        skill_dir: str | Path,
        expected_system: str = "boutique",
    ) -> "SymptomDagRegistry":
        """Load either canonical self-contained skills or legacy DAG cards.

        A directory must contain one format only. Canonical files are injected
        into the prompt without translating their four node concepts.
        """
        directory = Path(skill_dir).resolve()
        files = sorted(directory.glob("*.yaml"))
        if not files:
            raise ValueError(f"No symptom skill YAML files found in: {directory}")

        first_keys = set(_load_yaml(files[0]))
        if first_keys == SKILL_KEYS:
            return cls._load_normalized(files, expected_system)
        if first_keys == DAG_KEYS:
            return cls._load_legacy(files, expected_system)
        raise ValueError(
            f"Unsupported symptom skill format in {files[0]}; "
            f"keys={sorted(first_keys)}"
        )

    @classmethod
    def _load_normalized(
        cls,
        files: List[Path],
        expected_system: str,
    ) -> "SymptomDagRegistry":
        dags: Dict[str, SymptomDag] = {}
        prompt_skills: Dict[str, Dict[str, Any]] = {}

        for path in files:
            raw = _load_yaml(path)
            cls._require_exact_keys(raw, SKILL_KEYS, path)
            if raw["schema_version"] != 1:
                raise ValueError(f"schema_version must be 1: {path}")

            system = cls._required_string(raw["system"], "system", path)
            if system != expected_system:
                raise ValueError(f"Unsupported skill system {system!r} in {path}")
            symptom_id = cls._required_string(raw["symptom_id"], "symptom_id", path)
            if symptom_id in dags:
                raise ValueError(f"Duplicate symptom_id {symptom_id!r}: {path}")

            raw_nodes = raw["nodes"]
            if not isinstance(raw_nodes, dict) or not raw_nodes:
                raise ValueError(f"nodes must be a non-empty object: {path}")

            nodes: Dict[str, DagNode] = {}
            normalized_nodes: Dict[str, Dict[str, Any]] = {}
            for node_id, raw_node in raw_nodes.items():
                cls._required_string(node_id, "node_id", path)
                if not isinstance(raw_node, dict):
                    raise ValueError(f"Node {node_id} must be an object: {path}")
                cls._require_exact_keys(
                    raw_node,
                    SKILL_NODE_KEYS,
                    path,
                    context=f"node {node_id}",
                )
                goal = cls._required_string(
                    raw_node["goal"],
                    f"{node_id}.goal",
                    path,
                )
                evidence = _string_list(
                    raw_node["evidence"],
                    f"{node_id}.evidence",
                    path,
                    allow_empty=False,
                )
                next_atoms = _string_list(
                    raw_node["next"],
                    f"{node_id}.next",
                    path,
                )
                actions = cls._validate_actions(raw_node["actions"], node_id, path)
                nodes[node_id] = DagNode(
                    atom_id=node_id,
                    next_atoms=tuple(next_atoms),
                )
                normalized_nodes[node_id] = {
                    "goal": goal,
                    "actions": actions,
                    "evidence": evidence,
                    "next": next_atoms,
                }

            entries = tuple(
                _string_list(raw["entry"], "entry", path, allow_empty=False)
            )
            signals = tuple(
                _string_list(raw["signals"], "signals", path, allow_empty=False)
            )
            description = cls._required_string(
                raw["description"],
                "description",
                path,
            )
            dag = SymptomDag(
                system=system,
                symptom_id=symptom_id,
                # The canonical schema intentionally has no redundant display
                # name. The stable ID is sufficient for the selection catalog.
                name=symptom_id,
                description=description,
                surface_signals=signals,
                entry_atoms=entries,
                nodes=nodes,
            )
            cls._validate_graph(dag, path)
            dags[symptom_id] = dag
            prompt_skills[symptom_id] = {
                "schema_version": 1,
                "system": system,
                "symptom_id": symptom_id,
                "description": description,
                "signals": list(signals),
                "entry": list(entries),
                "nodes": normalized_nodes,
            }

        return cls(dags=dags, prompt_skills=prompt_skills)

    @classmethod
    def _load_legacy(
        cls,
        files: List[Path],
        expected_system: str,
    ) -> "SymptomDagRegistry":
        dags: Dict[str, SymptomDag] = {}
        prompt_skills: Dict[str, Dict[str, Any]] = {}
        shared_skills: Dict[str, AtomSkill] = {}
        skill_sources: Dict[str, Path] = {}

        for path in files:
            raw = _load_yaml(path)
            cls._require_exact_keys(raw, DAG_KEYS, path)
            system = cls._required_string(raw["system"], "system", path)
            if system != expected_system:
                raise ValueError(f"Unsupported DAG system {system!r} in {path}")
            symptom_id = cls._required_string(raw["symptom_id"], "symptom_id", path)
            if symptom_id in dags:
                raise ValueError(f"Duplicate symptom_id {symptom_id!r}: {path}")

            raw_nodes = raw["nodes"]
            if not isinstance(raw_nodes, dict) or not raw_nodes:
                raise ValueError(f"nodes must be a non-empty object: {path}")
            nodes: Dict[str, DagNode] = {}
            symptom_skills: Dict[str, AtomSkill] = {}
            for atom_id, raw_node in raw_nodes.items():
                if not isinstance(raw_node, dict):
                    raise ValueError(f"Node {atom_id} must be an object: {path}")
                cls._require_exact_keys(raw_node, NODE_KEYS, path, context=f"node {atom_id}")
                atom_path = (path.parent / str(raw_node["atom_file"])).resolve()
                skill = cls._load_legacy_atom(atom_path)
                if skill.atom_id != atom_id:
                    raise ValueError(
                        f"Node ID {atom_id!r} does not match atom_id "
                        f"{skill.atom_id!r}: {atom_path}"
                    )
                if atom_id in shared_skills and shared_skills[atom_id] != skill:
                    raise ValueError(
                        f"Atom {atom_id!r} has conflicting cards: "
                        f"{skill_sources[atom_id]} and {atom_path}"
                    )
                shared_skills[atom_id] = skill
                skill_sources[atom_id] = atom_path
                symptom_skills[atom_id] = skill
                nodes[atom_id] = DagNode(
                    atom_id=atom_id,
                    next_atoms=tuple(_string_list(raw_node["next"], "next", path)),
                )

            entries = tuple(
                _string_list(raw["entry_atoms"], "entry_atoms", path, allow_empty=False)
            )
            dag = SymptomDag(
                system=system,
                symptom_id=symptom_id,
                name=cls._required_string(raw["name"], "name", path),
                description=cls._required_string(
                    raw["description"],
                    "description",
                    path,
                ),
                surface_signals=tuple(
                    _string_list(raw["surface_signals"], "surface_signals", path)
                ),
                entry_atoms=entries,
                nodes=nodes,
            )
            cls._validate_graph(dag, path)
            dags[symptom_id] = dag
            prompt_skills[symptom_id] = {
                "symptom": {
                    "system": dag.system,
                    "symptom_id": dag.symptom_id,
                    "name": dag.name,
                    "description": dag.description,
                    "surface_signals": list(dag.surface_signals),
                },
                "entry_atoms": list(dag.entry_atoms),
                "graph": {
                    atom_id: list(node.next_atoms)
                    for atom_id, node in dag.nodes.items()
                },
                "skill_index": {
                    atom_id: symptom_skills[atom_id].to_prompt_dict()
                    for atom_id in dag.nodes
                },
            }

        return cls(dags=dags, prompt_skills=prompt_skills)

    @staticmethod
    def _required_string(value: Any, field: str, path: Path) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string: {path}")
        return value.strip()

    @staticmethod
    def _require_exact_keys(
        raw: Dict[str, Any],
        expected: set[str],
        path: Path,
        context: str = "document",
    ) -> None:
        actual = set(raw)
        if actual != expected:
            raise ValueError(
                f"Invalid keys in {context} at {path}; "
                f"missing={sorted(expected - actual)}, "
                f"extra={sorted(actual - expected)}"
            )

    @classmethod
    def _validate_actions(
        cls,
        value: Any,
        node_id: str,
        path: Path,
    ) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{node_id}.actions must be a list: {path}")
        actions: List[Dict[str, Any]] = []
        for index, action in enumerate(value):
            if not isinstance(action, dict):
                raise ValueError(f"{node_id}.actions[{index}] must be an object: {path}")
            cls._require_exact_keys(
                action,
                SKILL_ACTION_KEYS,
                path,
                context=f"{node_id}.actions[{index}]",
            )
            tool = cls._required_string(
                action["tool"],
                f"{node_id}.actions[{index}].tool",
                path,
            )
            args = action["args"]
            if not isinstance(args, dict):
                raise ValueError(f"{node_id}.actions[{index}].args must be an object: {path}")
            actions.append({"tool": tool, "args": copy.deepcopy(args)})
        return actions

    @classmethod
    def _load_legacy_atom(cls, path: Path) -> AtomSkill:
        raw = _load_yaml(path)
        cls._require_exact_keys(raw, ATOM_KEYS, path)
        return AtomSkill(
            atom_id=cls._required_string(raw["atom_id"], "atom_id", path),
            name=cls._required_string(raw["name"], "name", path),
            intent=cls._required_string(raw["intent"], "intent", path),
            core_action=cls._required_string(raw["core_action"], "core_action", path),
            optional_actions=tuple(
                _string_list(raw["optional_actions"], "optional_actions", path)
            ),
            expected_evidence=tuple(
                _string_list(raw["expected_evidence"], "expected_evidence", path)
            ),
        )

    @staticmethod
    def _validate_graph(dag: SymptomDag, path: Path) -> None:
        node_ids = set(dag.nodes)
        if not dag.entry_atoms or not set(dag.entry_atoms) <= node_ids:
            raise ValueError(f"entry contains missing nodes: {path}")
        for node in dag.nodes.values():
            missing = set(node.next_atoms) - node_ids
            if missing:
                raise ValueError(
                    f"Node {node.atom_id} references missing children {missing}: {path}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(atom_id: str) -> None:
            if atom_id in visiting:
                raise ValueError(f"Cycle detected at {atom_id}: {path}")
            if atom_id in visited:
                return
            visiting.add(atom_id)
            for child in dag.nodes[atom_id].next_atoms:
                visit(child)
            visiting.remove(atom_id)
            visited.add(atom_id)

        for entry in dag.entry_atoms:
            visit(entry)
        unreachable = node_ids - visited
        if unreachable:
            raise ValueError(f"Unreachable nodes {sorted(unreachable)}: {path}")

    def catalog(self) -> List[Dict[str, Any]]:
        return [self.dags[item].catalog_item() for item in sorted(self.dags)]

    def has_symptom(self, symptom_id: str) -> bool:
        return symptom_id in self.dags

    def diagnostic_graph_skill(self, symptom_id: str) -> Dict[str, Any]:
        """Return the complete prompt-ready skill for one selected symptom."""
        return copy.deepcopy(self._prompt_skills[symptom_id])
