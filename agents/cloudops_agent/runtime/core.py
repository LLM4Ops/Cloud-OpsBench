from __future__ import annotations

import ast
import inspect
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


SUPPORTED_SYSTEMS = {"boutique", "trainticket"}


def normalize_system(value: Any) -> str:
    system = str(value or "").strip().lower()
    if system == "train-ticket":
        system = "trainticket"
    if system not in SUPPORTED_SYSTEMS:
        raise ValueError(f"Unsupported diagnosis.system: {value!r}")
    return system


def load_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping")
    model = data.get("model")
    diagnosis = data.get("diagnosis")
    if not isinstance(model, dict) or not isinstance(diagnosis, dict):
        raise ValueError("Configuration requires model and diagnosis mappings")
    for key in ("model", "api_base", "api_key"):
        if not str(model.get(key) or "").strip():
            raise ValueError(f"model.{key} is required")
    diagnosis["system"] = normalize_system(diagnosis.get("system"))
    for key in ("fault_category", "dataset_root", "save_root"):
        if not str(diagnosis.get(key) or "").strip():
            raise ValueError(f"diagnosis.{key} is required")
    diagnosis["max_iterations"] = int(diagnosis.get("max_iterations", 20))
    if diagnosis["max_iterations"] < 1:
        raise ValueError("diagnosis.max_iterations must be positive")
    return data


@dataclass
class StepRecord:
    step_id: int
    prompt: str
    raw_model_output: str
    thought: Optional[str] = None
    action_type: Optional[str] = None
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
        return asdict(self)


@dataclass
class CaseState:
    case_id: str
    system_name: str
    question: str
    case_path: Optional[str] = None
    max_steps: int = 20
    current_step: int = 0
    finished: bool = False
    final_answer: Optional[str] = None
    stop_reason: Optional[str] = None
    history: List[StepRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
            "metadata": self.metadata,
            "steps": [step.to_dict() for step in self.history],
        }


def init_case_state(**kwargs: Any) -> CaseState:
    kwargs["system_name"] = normalize_system(kwargs["system_name"])
    return CaseState(**kwargs)


class OutputParser:
    _markdown_inside = re.compile(
        r"^\s*\*\*(Thought|Action|Action Input)\s*:\s*\*\*\s*",
        re.IGNORECASE | re.MULTILINE,
    )
    _markdown_outside = re.compile(
        r"^\s*\*\*(Thought|Action|Action Input)\s*\*\*\s*:\s*",
        re.IGNORECASE | re.MULTILINE,
    )
    _thought = re.compile(
        r"^Thought:\s*(.*?)(?=^Action:)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    _action = re.compile(r"^Action:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    _input = re.compile(r"^Action Input:\s*", re.IGNORECASE | re.MULTILINE)

    def parse(self, text: str) -> Dict[str, Any]:
        value = self._markdown_inside.sub(lambda m: f"{m.group(1)}: ", str(text).strip())
        value = self._markdown_outside.sub(lambda m: f"{m.group(1)}: ", value)
        action_match = self._action.search(value)
        input_match = self._input.search(value)
        if not action_match or not input_match:
            return self._invalid("Expected exactly one Action and Action Input block")
        try:
            action_input, tail = self._parse_input(value[input_match.end():].lstrip())
        except (json.JSONDecodeError, SyntaxError, ValueError) as exc:
            return self._invalid(f"Action Input is not a valid object: {exc}")
        if tail or not isinstance(action_input, dict):
            return self._invalid("Action Input must be one JSON object with no trailing text")
        thought = self._thought.search(value)
        return {
            "type": "tool",
            "thought": thought.group(1).strip() if thought else None,
            "action_name": action_match.group(1).strip(),
            "action_input": action_input,
            "error": None,
        }

    @staticmethod
    def _parse_input(value: str) -> tuple[Any, str]:
        decoder = json.JSONDecoder()
        try:
            parsed, end = decoder.raw_decode(value)
            return parsed, value[end:].strip()
        except json.JSONDecodeError as error:
            try:
                return ast.literal_eval(value), ""
            except (SyntaxError, ValueError):
                raise error

    @staticmethod
    def validate_submit_payload(value: Dict[str, Any]) -> str | None:
        if not isinstance(value.get("key_evidence_summary"), str) or not value["key_evidence_summary"].strip():
            return "Submit requires a non-empty key_evidence_summary"
        predictions = value.get("top_3_predictions")
        if not isinstance(predictions, list) or len(predictions) != 3:
            return "Submit requires exactly three top_3_predictions"
        for index, prediction in enumerate(predictions, 1):
            if not isinstance(prediction, dict):
                return f"Prediction {index} must be an object"
            if prediction.get("rank") != index:
                return f"Prediction {index} must have rank={index}"
            for key in ("fault_object", "root_cause"):
                if not isinstance(prediction.get(key), str) or not prediction[key].strip():
                    return f"Prediction {index} requires non-empty {key}"
        return None

    @staticmethod
    def _invalid(error: str) -> Dict[str, Any]:
        return {"type": "invalid", "thought": None, "action_name": None,
                "action_input": None, "error": error}


class TraceLogger:
    def __init__(self, trace_dir: Path | str):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def get_trace_path(self, state: CaseState) -> Path:
        return self.trace_dir / f"{state.case_id}.json"

    def save_case_state(self, state: CaseState) -> str:
        path = self.get_trace_path(state)
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


class ToolExecutor:
    def __init__(self, tool_registry: Dict[str, Any]):
        self.tool_registry = tool_registry

    def execute(self, action_name: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        if action_name not in self.tool_registry:
            return {"success": False, "observation": None,
                    "error": f"Unknown tool: {action_name}", "latency": 0.0}
        try:
            tool = self.tool_registry[action_name]
            schema = getattr(tool, "args_schema", None)
            if schema is not None and hasattr(schema, "model_fields"):
                allowed = set(schema.model_fields)
            else:
                signature = inspect.signature(tool._run)
                allowed = set(signature.parameters)
            filtered = {key: item for key, item in action_input.items() if key in allowed}
            observation = tool._run(**filtered)
            return {"success": True, "observation": "" if observation is None else str(observation),
                    "error": None, "latency": time.perf_counter() - start}
        except Exception as exc:
            return {"success": False, "observation": None,
                    "error": f"Tool execution failed for {action_name}: {exc}",
                    "latency": time.perf_counter() - start}
