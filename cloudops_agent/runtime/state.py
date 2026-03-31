# runtime/state.py

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepRecord:
    """
    Record for a single ReAct step.

    One step corresponds to:
    - prompt construction
    - model generation
    - parsing
    - optional tool execution
    - observation / error capture
    """

    step_id: int
    prompt: str
    raw_model_output: str

    thought: Optional[str] = None
    action_type: Optional[str] = None  # "tool" | "finish" | "invalid"
    action_name: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = None

    observation: Optional[str] = None
    error: Optional[str] = None

    model_latency: Optional[float] = None
    tool_latency: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the step record into a plain dictionary."""
        return asdict(self)


@dataclass
class CaseState:
    """
    Runtime state for one Cloud-OpsBench case.
    """

    case_id: str
    system_name: str
    question: str
    case_path: Optional[str] = None

    max_steps: int = 10
    current_step: int = 0
    finished: bool = False

    final_answer: Optional[str] = None
    stop_reason: Optional[str] = None
    ground_truth: Optional[Dict[str, Any]] = None

    history: List[StepRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full case state into a plain dictionary."""
        return {
            "case_id": self.case_id,
            "system_name": self.system_name,
            "question": self.question,
            "case_path": self.case_path,
            "max_steps": self.max_steps,
            "current_step": self.current_step,
            "finished": self.finished,
            "final_answer": self.final_answer,
            "stop_reason": self.stop_reason,
            "ground_truth": self.ground_truth,
            "metadata": self.metadata,
            "steps": [step.to_dict() for step in self.history],
        }


def init_case_state(
    case_id: str,
    system_name: str,
    question: str,
    case_path: Optional[str] = None,
    max_steps: int = 10,
    ground_truth: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> CaseState:
    """
    Create an initialized CaseState object.

    Args:
        case_id: Unique case identifier.
        system_name: System name, e.g. 'train-ticket' or 'online-boutique'.
        question: Diagnosis question shown to the agent.
        case_path: Path to the underlying snapshot/case data.
        max_steps: Maximum ReAct steps allowed.
        ground_truth: Optional gold diagnosis result for the case.
        metadata: Optional extra metadata for analysis.

    Returns:
        A fully initialized CaseState.
    """
    return CaseState(
        case_id=case_id,
        system_name=system_name,
        question=question,
        case_path=case_path,
        max_steps=max_steps,
        ground_truth=ground_truth,
        metadata=metadata or {},
    )


def append_step(state: CaseState, step_record: StepRecord) -> None:
    """
    Append one step record to the case history.

    Args:
        state: The mutable case state.
        step_record: One fully constructed step record.
    """
    state.history.append(step_record)
