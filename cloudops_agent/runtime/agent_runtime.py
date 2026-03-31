# runtime/agent_runtime.py

from __future__ import annotations

from .state import CaseState, StepRecord, append_step


class AgentRuntime:
    """
    Minimal single-agent ReAct runtime.

    Responsibilities:
    - build prompt from current state
    - call model
    - parse model output
    - execute tool if needed
    - record every step
    - persist trace after each step
    """

    def __init__(
        self,
        prompt_builder,
        model_runner,
        output_parser,
        tool_executor,
        trace_logger,
    ):
        """
        Args:
            prompt_builder: PromptBuilder instance
            model_runner: ModelRunner instance
            output_parser: OutputParser instance
            tool_executor: ToolExecutor instance
            trace_logger: TraceLogger instance
        """
        self.prompt_builder = prompt_builder
        self.model_runner = model_runner
        self.output_parser = output_parser
        self.tool_executor = tool_executor
        self.trace_logger = trace_logger

    def run_case(self, state: CaseState) -> CaseState:
        """
        Run a single case until finish or max_steps.

        Args:
            state: Initialized case state.

        Returns:
            Final case state after execution.
        """
        while not state.finished and state.current_step < state.max_steps:
            step_record = self._run_one_step(state)
            append_step(state, step_record)

            if step_record.action_type == "finish":
                state.finished = True
                state.final_answer = step_record.final_answer
                state.stop_reason = "final_answer"

            # Save trace after every step
            self.trace_logger.save_case_state(state)

            # Advance step counter after saving
            state.current_step += 1

        if not state.finished and state.current_step >= state.max_steps:
            state.stop_reason = "max_steps"
            self.trace_logger.save_case_state(state)

        return state

    def _run_one_step(self, state: CaseState) -> StepRecord:
        """
        Run one ReAct step.

        Flow:
        1. build prompt
        2. call model
        3. parse output
        4. if tool action, execute tool
        5. construct StepRecord

        Args:
            state: Current case state.

        Returns:
            One fully populated StepRecord.
        """
        step_id = state.current_step + 1
        prompt = self.prompt_builder.build(state)

        # 1) Call model
        raw_model_output = ""
        model_latency = None
        input_tokens = None
        output_tokens = None

        try:
            model_result = self.model_runner.generate(prompt)
            raw_model_output = model_result.get("text", "")
            model_latency = model_result.get("latency")
            input_tokens = model_result.get("input_tokens")
            output_tokens = model_result.get("output_tokens")
        except Exception as e:
            return StepRecord(
                step_id=step_id,
                prompt=prompt,
                raw_model_output=raw_model_output,
                thought=None,
                action_type="invalid",
                action_name=None,
                action_input=None,
                final_answer=None,
                observation=None,
                error=f"ModelRunner error: {e}",
                model_latency=model_latency,
                tool_latency=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # 2) Parse output
        parsed = self.output_parser.parse(raw_model_output)

        thought = parsed.get("thought")
        action_type = parsed.get("type")
        action_name = parsed.get("action_name")
        action_input = parsed.get("action_input")
        final_answer = parsed.get("final_answer")
        parse_error = parsed.get("error")

        # 3) Final answer path
        if action_type == "finish":
            return StepRecord(
                step_id=step_id,
                prompt=prompt,
                raw_model_output=raw_model_output,
                thought=thought,
                action_type="finish",
                action_name=None,
                action_input=None,
                final_answer=final_answer,
                observation=None,
                error=None,
                model_latency=model_latency,
                tool_latency=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # 4) Invalid path
        if action_type == "invalid":
            return StepRecord(
                step_id=step_id,
                prompt=prompt,
                raw_model_output=raw_model_output,
                thought=thought,
                action_type="invalid",
                action_name=action_name,
                action_input=action_input,
                final_answer=None,
                observation=None,
                error=parse_error or "Invalid model output.",
                model_latency=model_latency,
                tool_latency=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # 5) Tool execution path
        tool_result = self.tool_executor.execute(action_name, action_input)

        observation = tool_result.get("observation")
        tool_error = tool_result.get("error")
        tool_latency = tool_result.get("latency")

        return StepRecord(
            step_id=step_id,
            prompt=prompt,
            raw_model_output=raw_model_output,
            thought=thought,
            action_type="tool",
            action_name=action_name,
            action_input=action_input,
            final_answer=None,
            observation=observation,
            error=tool_error,
            model_latency=model_latency,
            tool_latency=tool_latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )