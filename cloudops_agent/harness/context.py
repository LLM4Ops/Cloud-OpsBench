from __future__ import annotations

from pathlib import Path

from runtime.core import CaseState, StepRecord


class ContextBuilder:
    """Build the complete text prompt while retaining the full ReAct history."""

    def __init__(self, *, tools_description: str, expected_output: str):
        self.tools_description = tools_description
        self.expected_output = expected_output
        self.system_prompt = Path(__file__).with_name("system_prompt.md").read_text(
            encoding="utf-8"
        ).strip()

    def build(self, state: CaseState) -> str:
        sections = [
            self.system_prompt,
            "## Available Tools\nYou may use exactly one tool per step.\n"
            + self.tools_description,
            "## Final Diagnosis Output Requirement\n"
            "When you decide to finish, call `Submit`. Its Action Input must "
            "strictly follow this specification.\n"
            + self.expected_output.strip(),
            self._history(state),
            "## Current Case\n"
            f"Question: {state.question}\n"
            f"Current Step: {state.current_step + 1}\n"
            f"Budget Steps: {state.max_steps}",
        ]
        return "\n\n".join(section for section in sections if section.strip())

    @staticmethod
    def _history(state: CaseState) -> str:
        if not state.history:
            return "## Previous Steps\nNone yet."
        return "## Previous Steps\n\n" + "\n\n".join(
            ContextBuilder._format_step(step) for step in state.history
        )

    @staticmethod
    def _format_step(step: StepRecord) -> str:
        parts = [f"Step {step.step_id}"]
        if step.thought:
            parts.append(f"Thought: {step.thought}")
        if step.action_type in {"tool", "submit"}:
            parts.append(f"Action: {step.action_name}")
            parts.append(f"Action Input: {step.action_input}")
        if step.observation is not None:
            parts.append(f"Observation: {step.observation}")
        if step.error:
            parts.append(f"Error: {step.error}")
        return "\n".join(parts)
