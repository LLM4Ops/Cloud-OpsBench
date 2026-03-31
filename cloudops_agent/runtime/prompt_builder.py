from __future__ import annotations

from typing import List, Optional

from runtime.state import CaseState, StepRecord


class PromptBuilder:
    """
    Build prompts for the lightweight single-agent ReAct runtime.

    Prompt structure:
    1. Runtime-level minimal instruction
    2. Agent backstory / diagnosis policy
    3. Current case context
    4. Available tools
    5. Expected final output specification
    6. Previous steps
    7. Current step output protocol
    """

    def __init__(
        self,
        tools_description: str,
        backstory_prompt: Optional[str] = None,
        expected_output: Optional[str] = None,
    ):
        """
        Args:
            tools_description: Human-readable tool descriptions.
            backstory_prompt: Main diagnosis policy prompt (e.g. agent_prompt / cot / rag / icl).
            expected_output: Final answer specification, usually strict JSON instructions.
        """
        self.tools_description = tools_description
        self.backstory_prompt = backstory_prompt or ""
        self.expected_output = expected_output or ""

    def build(self, state: CaseState) -> str:
        """
        Build the full prompt for the current step.
        """
        sections: List[str] = [
            # self._build_runtime_instruction(),
            self._build_backstory_section(),
            self._build_tools_section(),
            self._build_expected_output_section(),
            self._build_history_section(state),
            self._build_case_section(state),
            self._build_current_step_instruction(state),
        ]
        return "\n\n".join(section for section in sections if section.strip())

    def _build_runtime_instruction(self) -> str:
        """
        Minimal runtime-level instruction.

        Keep this section short. Avoid repeating detailed diagnosis principles,
        because those belong to `agent_prompt`.
        """
        return (
            "## Runtime Instruction\n"
            "You are interacting with a diagnostic runtime for cloud incident root cause analysis.\n"
            "You must collect evidence through tools step by step.\n"
            "You are not allowed to fabricate system observations.\n"
            "At each step, you must do exactly one of the following:\n"
            "1. Call exactly one tool, or\n"
            "2. Produce the final diagnosis output if the root cause has been clearly identified.\n"
        )

    def _build_backstory_section(self) -> str:
        """
        Main diagnosis policy prompt, such as agent_prompt / CoT prompt / RAG prompt / ICL prompt.
        """
        if not self.backstory_prompt:
            return ""
        return self.backstory_prompt.strip()

    def _build_case_section(self, state: CaseState) -> str:
        """
        Build current case context.
        """
        lines = [
            "## Current Case",
            f"Question: {state.question}",
            f"Current Step: {state.current_step + 1}",
            f"Budget Steps: {state.max_steps}"
             # You must output the final diagnosis before this, otherwise it will be regarded as task failure",
        ]

        # if state.case_path:
        #     lines.append(f"Case Path: {state.case_path}")

        # if state.metadata:
        #     lines.append("Metadata:")
        #     for key, value in state.metadata.items():
        #         lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    def _build_tools_section(self) -> str:
        """
        Build available tools section.
        """
        return (
            "## Available Tools\n"
            "You may use exactly one tool per step.\n"
            f"{self.tools_description}"
        )

    def _build_expected_output_section(self) -> str:
        """
        Build final output requirements section.

        This section defines what the final answer must look like.
        """
        if not self.expected_output:
            return ""
        return (
            "## Final Diagnosis Output Requirement\n"
            "When you have clearly identified the root cause and decide to finish, "
            "your final response MUST strictly follow the specification below.\n"
            f"{self.expected_output.strip()}"
        )

    def _build_history_section(self, state: CaseState) -> str:
        """
        Build previous trajectory history.

        MVP version includes all prior steps in plain text.
        """
        if not state.history:
            return "## Previous Steps\nNone yet."

        lines = ["## Previous Steps"]
        for step in state.history:
            lines.append(self._format_step(step))
        return "\n\n".join(lines)

    def _format_step(self, step: StepRecord) -> str:
        """
        Format one step into text for prompt context.
        """
        parts = [f"Step {step.step_id}"]

        if step.thought:
            parts.append(f"Thought: {step.thought}")

        if step.action_type == "tool":
            parts.append(f"Action: {step.action_name}")
            parts.append(f"Action Input: {step.action_input}")

        if step.observation is not None:
            parts.append(f"Observation: {step.observation}")

        if step.error:
            parts.append(f"Error: {step.error}")

        if step.action_type == "finish" and step.final_answer:
            parts.append(f"Final Output: {step.final_answer}")

        return "\n".join(parts)

    def _build_current_step_instruction(self, state: CaseState) -> str:
        return (
            "## Output Protocol\n"
            "At this step, follow these rules strictly:\n\n"
            "1. If you still need more evidence, you MUST output exactly one tool call using this format:\n"
            "Thought: <brief reasoning>\n"
            "Action: <tool_name>\n"
            "Action Input: <valid JSON object>\n\n"
            "Example:\n"
            "Thought: I should inspect the pod states first.\n"
            "Action: GetResources\n"
            'Action Input: {"resource_type": "pods", "namespace": "your-namespace"}\n\n'
            "2. Action Input must strictly follow the parameter schema shown for that tool.\n"
            "3. Action Input keys must exactly match the tool parameter names.\n"
            "4. Do not invent parameter names.\n"
            "5. If a tool takes no parameters, Action Input must be {}.\n\n"
            "6. If and only if you have already identified the root cause with sufficient evidence, "
            "you MUST STOP calling tools and output the final diagnosis JSON only.\n"
            "7. Do NOT continue re-checking the same evidence once the root cause is already clear.\n"
            "8. Do NOT mix tool-call format with final JSON output.\n\n"
            "When stopping, the output must be JSON only, for example:\n"
            "```json\n"
            "{\n"
            '  "key_evidence_summary": "...",\n'
            '  "top_3_predictions": [\n'
            "    {\n"
            '      "rank": 1,\n'
            '      "fault_taxonomy": "...",\n'
            '      "fault_object": "...",\n'
            '      "root_cause": "..."\n'
            "    },\n"
            "    {\n"
            '      "rank": 2,\n'
            '      "fault_taxonomy": "...",\n'
            '      "fault_object": "...",\n'
            '      "root_cause": "..."\n'
            "    },\n"
            "    {\n"
            '      "rank": 3,\n'
            '      "fault_taxonomy": "...",\n'
            '      "fault_object": "...",\n'
            '      "root_cause": "..."\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
        )
