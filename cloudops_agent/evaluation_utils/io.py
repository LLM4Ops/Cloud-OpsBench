from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .matcher import observation_to_text, parse_cache_key, parse_golden_calling
from .schema import CaseAnnotation, TrajectoryStep


def load_annotation(path: str | Path) -> CaseAnnotation:
    with Path(path).open("r", encoding="utf-8") as fh:
        return CaseAnnotation.from_dict(json.load(fh))


def load_annotations(path: str | Path) -> List[CaseAnnotation]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, Mapping) and "cases" in data:
        return [CaseAnnotation.from_dict(item) for item in data["cases"]]
    if isinstance(data, Mapping) and "case_id" in data:
        return [CaseAnnotation.from_dict(data)]
    if isinstance(data, list):
        return [CaseAnnotation.from_dict(item) for item in data]
    raise ValueError("Annotation file must be a list or an object with a 'cases' field")


def load_golden_trajectory(path: str | Path) -> List[TrajectoryStep]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    trace = data.get("diagnostic_trace", [])
    steps: List[TrajectoryStep] = []
    for item in trace:
        tool_name = item.get("tool_name", "")
        calling = item.get("calling", "")
        tool_call = parse_golden_calling(calling, fallback_tool_name=tool_name)
        steps.append(TrajectoryStep(tool_call=tool_call, observation=item.get("output", "")))
    return steps


def load_tool_cache(path: str | Path) -> List[TrajectoryStep]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    steps: List[TrajectoryStep] = []
    for key, observation in data.items():
        if key == "collection_timestamp":
            continue
        steps.append(TrajectoryStep(tool_call=parse_cache_key(key), observation=observation))
    return steps


def build_tool_cache_index(path: str | Path, preview_chars: int = 240) -> List[Dict[str, Any]]:
    """Build a compact index without expanding full observations into prompts."""

    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    index: List[Dict[str, Any]] = []
    for key, observation in data.items():
        if key == "collection_timestamp":
            continue
        call = parse_cache_key(key)
        text = observation_to_text(observation)
        index.append(
            {
                "cache_key": key,
                "tool_name": call.tool_name,
                "arguments": dict(call.arguments),
                "observation_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "observation_chars": len(text),
                "preview": _preview(text, preview_chars),
            }
        )
    return index


def _preview(text: str, preview_chars: int) -> str:
    one_line = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return one_line[:preview_chars]
