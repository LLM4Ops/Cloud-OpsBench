from __future__ import annotations

import json

from runtime.core import CaseState, StepRecord

from .hooks import HarnessHooks


class CloudOpsHarness:
    """Skill-free single-agent ReAct loop for Cloud-OpsBench."""

    def __init__(self, *, context_builder, model_runner, output_parser,
                 tool_executor, trace_logger, hooks: HarnessHooks | None = None):
        self.context_builder = context_builder
        self.model_runner = model_runner
        self.output_parser = output_parser
        self.tool_executor = tool_executor
        self.trace_logger = trace_logger
        self.hooks = hooks or HarnessHooks()

    def run_case(self, state: CaseState) -> CaseState:
        if state.current_step or state.history:
            raise ValueError("CloudOpsHarness requires a fresh CaseState")
        while not state.finished and state.current_step < state.max_steps:
            step = self._run_step(state)
            state.history.append(step)
            state.current_step += 1
            if step.action_type == "submit" and not step.error:
                state.finished = True
                state.final_answer = step.final_answer
                state.stop_reason = "submit"
            self.trace_logger.save_case_state(state)
        if not state.finished:
            state.stop_reason = "max_steps"
            self.trace_logger.save_case_state(state)
        return state

    def _run_step(self, state: CaseState) -> StepRecord:
        prompt = self.context_builder.build(state)
        common = {"step_id": state.current_step + 1, "prompt": prompt}
        try:
            generated = self.model_runner.generate(prompt)
        except Exception as exc:
            return StepRecord(**common, raw_model_output="", action_type="invalid",
                              error=f"ModelRunner error: {exc}")
        raw = generated.get("text", "")
        parsed = self.output_parser.parse(raw)
        common.update(
            raw_model_output=raw,
            thought=parsed.get("thought"),
            model_latency=generated.get("latency"),
            input_tokens=generated.get("input_tokens"),
            output_tokens=generated.get("output_tokens"),
        )
        if parsed.get("type") != "tool":
            return StepRecord(**common, action_type="invalid", error=parsed.get("error"))

        name = parsed["action_name"]
        arguments = parsed["action_input"]
        name, arguments = self.hooks.before_action(state, name, arguments)
        if name == "Submit":
            error = self.output_parser.validate_submit_payload(arguments)
            observation = json.dumps(
                {"error": error} if error else {"submitted": True}, ensure_ascii=False
            )
            return self.hooks.after_action(
                state,
                StepRecord(**common, action_type="submit", action_name=name,
                           action_input=arguments, observation=observation, error=error,
                           final_answer=None if error else json.dumps(arguments, ensure_ascii=False)),
            )

        result = self.tool_executor.execute(name, arguments)
        return self.hooks.after_action(
            state,
            StepRecord(**common, action_type="tool", action_name=name,
                       action_input=arguments, observation=result.get("observation"),
                       error=result.get("error"), tool_latency=result.get("latency")),
        )
