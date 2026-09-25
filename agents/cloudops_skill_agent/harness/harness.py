from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from runtime.core import CaseState, StepRecord

from .hooks import HarnessHooks


SUPPORTED_SYSTEMS = {"boutique", "trainticket"}


class CloudOpsHarness:
    """ReAct loop with explicit symptom selection and diagnosis submission."""

    def __init__(
        self,
        prompt_builder,
        model_runner,
        output_parser,
        tool_executor,
        trace_logger,
        symptom_registry,
        hooks: HarnessHooks | None = None,
    ):
        self.prompt_builder = prompt_builder
        self.model_runner = model_runner
        self.output_parser = output_parser
        self.tool_executor = tool_executor
        self.trace_logger = trace_logger
        self.symptom_registry = symptom_registry
        self.hooks = hooks or HarnessHooks()

    def run_case(self, state: CaseState) -> CaseState:
        if state.system_name not in SUPPORTED_SYSTEMS:
            raise ValueError(
                "cloudops_agent_h0 supports system_name in "
                f"{sorted(SUPPORTED_SYSTEMS)}."
            )
        if state.current_step != 0 or state.history:
            raise ValueError("H0 runtime expects a fresh CaseState.")

        while not state.finished and state.current_step < state.max_steps:
            step = self._run_agent_step(state)
            state.history.append(step)
            state.current_step += 1

            if step.action_type == "submit" and not step.error:
                state.finished = True
                state.final_answer = step.final_answer
                state.stop_reason = "submit"
            self.trace_logger.save_case_state(state)

        if not state.finished and state.current_step >= state.max_steps:
            state.stop_reason = "max_steps"
            self.trace_logger.save_case_state(state)
        return state

    def _run_agent_step(self, state: CaseState) -> StepRecord:
        step_id = state.current_step + 1
        prompt = self.prompt_builder.build(state)
        raw_output = ""
        latency = input_tokens = output_tokens = None
        try:
            result = self.model_runner.generate(prompt)
            raw_output = result.get("text", "")
            latency = result.get("latency")
            input_tokens = result.get("input_tokens")
            output_tokens = result.get("output_tokens")
        except Exception as exc:
            return StepRecord(
                step_id=step_id,
                prompt=prompt,
                raw_model_output=raw_output,
                action_type="invalid",
                error=f"ModelRunner error: {exc}",
            )

        parsed = self.output_parser.parse(raw_output)
        common = {
            "step_id": step_id,
            "prompt": prompt,
            "raw_model_output": raw_output,
            "thought": parsed.get("thought"),
            "model_latency": latency,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        if parsed.get("type") != "tool":
            return StepRecord(
                **common,
                action_type="invalid",
                action_name=parsed.get("action_name"),
                action_input=parsed.get("action_input"),
                error=parsed.get("error") or "Invalid model output.",
            )

        action_name = parsed.get("action_name")
        action_input = parsed.get("action_input") or {}
        action_name, action_input = self.hooks.before_action(
            state, action_name, action_input
        )
        if action_name == "SelectSymptom":
            observation, error = self._execute_internal(action_name, action_input, state)
            return self.hooks.after_action(state, StepRecord(
                **common,
                action_type="internal",
                action_name=action_name,
                action_input=action_input,
                observation=observation,
                error=error,
            ))
        if action_name == "Submit":
            error = self.output_parser.validate_submit_payload(action_input)
            observation = (
                json.dumps({"error": error}, ensure_ascii=False)
                if error
                else json.dumps({"submitted": True}, ensure_ascii=False)
            )
            return self.hooks.after_action(state, StepRecord(
                **common,
                action_type="submit",
                action_name=action_name,
                action_input=action_input,
                final_answer=(
                    None if error else json.dumps(action_input, ensure_ascii=False)
                ),
                observation=observation,
                error=error,
            ))

        tool_result = self.tool_executor.execute(action_name, action_input)
        return self.hooks.after_action(state, StepRecord(
            **common,
            action_type="tool",
            action_name=action_name,
            action_input=action_input,
            observation=tool_result.get("observation"),
            error=tool_result.get("error"),
            tool_latency=tool_result.get("latency"),
        ))

    def _execute_internal(
        self, action_name: str, action_input: Dict[str, Any], state: CaseState
    ) -> Tuple[str, str | None]:
        symptom_id = action_input.get("symptom_id")
        if not isinstance(symptom_id, str) or not self.symptom_registry.has_symptom(
            symptom_id
        ):
            error = (
                "SelectSymptom requires an exact symptom_id from the catalog; "
                "no fuzzy or evidence-based matching is performed."
            )
            payload = {
                "error": error,
                "available_symptom_ids": sorted(self.symptom_registry.dags),
            }
            return json.dumps(payload, ensure_ascii=False), error
        previous_symptom_id = state.active_symptom_id
        state.active_symptom_id = symptom_id
        state.symptom_selection_history.append(symptom_id)
        return (
            json.dumps(
                {
                    "selected_symptom_id": symptom_id,
                    "replaced_symptom_id": previous_symptom_id,
                    "diagnostic_graph_skill_loaded": True,
                    "message": (
                        "The complete selected Diagnostic Graph Skill will be "
                        "included in the next prompt."
                    ),
                },
                ensure_ascii=False,
            ),
            None,
        )
