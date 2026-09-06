from __future__ import annotations

from typing import Any, Dict, Tuple

from runtime.core import CaseState, StepRecord


class HarnessHooks:
    """Evolution surface for action lifecycle hooks.

    The H0 implementation is intentionally identity/no-op so enabling the hook
    calls does not change the baseline agent behavior.
    """

    def before_action(
        self,
        state: CaseState,
        action_name: str,
        action_input: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        return action_name, action_input

    def after_action(self, state: CaseState, step: StepRecord) -> StepRecord:
        return step
