from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from runtime.core import CaseState, StepRecord
from runtime.skills import SymptomDagRegistry


class ContextBuilder:
    """
    Build prompts for the lightweight H0 ReAct runtime.

    Static instructions live in system_prompt.md. Render its named sections
    around runtime data while preserving the baseline prompt layout.
    """

    def __init__(
        self,
        tools_description: str,
        symptom_registry: SymptomDagRegistry,
        backstory_prompt: Optional[str] = None,
        expected_output: Optional[str] = None,
    ):
        self.tools_description = tools_description
        self.symptom_registry = symptom_registry
        self.backstory_prompt = backstory_prompt or ""
        self.expected_output = expected_output or ""
        self._prompt_sections = self._parse_prompt_sections(
            Path(__file__).with_name("system_prompt.md").read_text(encoding="utf-8")
        )

    @staticmethod
    def _parse_prompt_sections(text: str) -> dict[str, str]:
        """Use five stable Markdown headings as section boundaries.

        Other headings remain part of their surrounding section. Missing or
        duplicate required headings fail explicitly instead of dropping rules.
        """
        headings = (
            "Available Tools", "Symptom Selection", "Diagnostic Graph Skill",
            "Final Diagnosis Output Requirement", "Output Protocol",
        )
        positions = []
        for heading in headings:
            matches = list(re.finditer(r"^## " + re.escape(heading) + r"$", text, re.MULTILINE))
            if len(matches) != 1:
                raise ValueError(f"system_prompt.md must contain exactly one '## {heading}' heading")
            positions.append((matches[0].start(), heading))
        positions.sort()
        sections = {"role": text[:positions[0][0]].strip()}
        for index, (start, heading) in enumerate(positions):
            end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
            sections[heading] = text[start:end].strip()
        return sections

    @classmethod
    def from_system_prompt(
        cls,
        tools_description: str,
        symptom_registry: SymptomDagRegistry,
        expected_output: str,
    ) -> "ContextBuilder":
        builder = cls(
            tools_description=tools_description,
            symptom_registry=symptom_registry,
            expected_output=expected_output,
        )
        builder.backstory_prompt = builder._prompt_sections["role"]
        return builder

    def build(self, state: CaseState) -> str:
        sections: List[str] = [
            self._build_backstory_section(),
            self._build_tools_section(),
            self._build_symptom_section(state),
            self._build_expected_output_section(),
            self._build_history_section(state),
            self._build_case_section(state),
            self._prompt_sections["Output Protocol"] + "\n",
        ]
        return "\n\n".join(section for section in sections if section.strip())

    def _build_backstory_section(self) -> str:
        if not self.backstory_prompt:
            return ""
        return self.backstory_prompt.strip()

    def _build_tools_section(self) -> str:
        return (
            f"{self._prompt_sections['Available Tools']}\n"
            f"{self.tools_description}"
        )

    def _build_symptom_section(self, state: CaseState) -> str:
        lines = [
            self._prompt_sections["Symptom Selection"],
            "",
            "Symptom catalog:",
            json.dumps(
                [
                    {
                        "symptom_id": item["symptom_id"],
                        "description": item["description"],
                    }
                    for item in self.symptom_registry.catalog()
                ],
                ensure_ascii=False,
                indent=2,
            ),
        ]

        if not state.active_symptom_id:
            lines.extend(
                [
                    "",
                    "Active symptom: none",
                    "No Diagnostic Graph Skill is loaded yet.",
                ]
            )
            return "\n".join(lines)

        graph_skill = self.symptom_registry.diagnostic_graph_skill(
            state.active_symptom_id
        )
        lines.extend(
            [
                "",
                f"Active symptom: {state.active_symptom_id}",
                "",
                self._prompt_sections["Diagnostic Graph Skill"],
                self._render_graph_skill(graph_skill),
            ]
        )
        return "\n".join(lines)

    def _render_graph_skill(self, graph_skill: dict) -> str:
        nodes = graph_skill.get("nodes") or {}
        entry = graph_skill.get("entry") or graph_skill.get("entry_atoms") or []
        graph = graph_skill.get("graph") or {
            node_id: node.get("next", []) for node_id, node in nodes.items()
        }

        lines = [
            "Graph Index:",
            f"- symptom_id: {graph_skill.get('symptom_id')}",
            "- entry:",
        ]
        lines.extend(f"  - {node_id}" for node_id in entry)
        lines.append("- routes:")
        for node_id in nodes:
            next_nodes = graph.get(node_id, [])
            if next_nodes:
                lines.append(f"  - {node_id} -> {', '.join(next_nodes)}")
            else:
                lines.append(f"  - {node_id} -> <terminal>")

        lines.append("")
        lines.append("Node Details:")
        for node_id, node in nodes.items():
            lines.append(f"[{node_id}]")
            goal = self._node_field(node, "goal") or self._node_field(node, "intent")
            lines.append(f"goal: {goal}")
            lines.append("actions:")
            for action in self._node_actions(node):
                lines.append(f"- {action}")
            lines.append("evidence:")
            for evidence in self._node_list(node, "evidence", "expected_evidence"):
                lines.append(f"- {evidence}")
            lines.append("next:")
            next_nodes = graph.get(node_id, [])
            if next_nodes:
                lines.extend(f"- {next_node}" for next_node in next_nodes)
            else:
                lines.append("- <terminal>")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def _node_field(node: dict, *keys: str) -> str:
        for key in keys:
            value = node.get(key)
            if isinstance(value, str):
                return value
        return ""

    @staticmethod
    def _node_list(node: dict, *keys: str) -> list:
        for key in keys:
            value = node.get(key)
            if isinstance(value, list):
                return value
        return []

    def _node_actions(self, node: dict) -> list:
        actions = node.get("actions")
        if isinstance(actions, list):
            return [self._format_action(action) for action in actions]
        legacy_actions = []
        if node.get("core_action"):
            legacy_actions.append(str(node["core_action"]))
        legacy_actions.extend(str(action) for action in node.get("optional_actions", []))
        return legacy_actions

    @staticmethod
    def _format_action(action: object) -> str:
        if not isinstance(action, dict):
            return str(action)
        tool = action.get("tool") or action.get("name") or "<tool>"
        reason = action.get("reason")
        arguments = (
            action.get("arguments")
            or action.get("args")
            or action.get("input")
            or action.get("parameters")
        )
        parts = [str(tool)]
        if arguments is not None:
            parts.append(json.dumps(arguments, ensure_ascii=False))
        if reason:
            parts.append(f"- {reason}")
        return " ".join(parts)

    def _build_expected_output_section(self) -> str:
        if not self.expected_output:
            return ""
        return (
            f"{self._prompt_sections['Final Diagnosis Output Requirement']}\n"
            f"{self.expected_output.strip()}"
        )

    def _build_history_section(self, state: CaseState) -> str:
        if not state.history:
            return "## Previous Steps\nNone yet."
        lines = ["## Previous Steps"]
        for step in state.history:
            lines.append(self._format_step(step))
        return "\n\n".join(lines)

    @staticmethod
    def _format_step(step: StepRecord) -> str:
        parts = [f"Step {step.step_id}"]
        if step.thought:
            parts.append(f"Thought: {step.thought}")
        if step.action_type in {"tool", "internal", "submit"}:
            parts.append(f"Action: {step.action_name}")
            parts.append(f"Action Input: {step.action_input}")
        if step.observation is not None:
            parts.append(f"Observation: {step.observation}")
        if step.error:
            parts.append(f"Error: {step.error}")
        return "\n".join(parts)

    @staticmethod
    def _build_case_section(state: CaseState) -> str:
        return (
            "## Current Case\n"
            f"Question: {state.question}\n"
            f"Current Step: {state.current_step + 1}\n"
            f"Budget Steps: {state.max_steps}"
        )
