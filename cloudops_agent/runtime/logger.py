# runtime/logger.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from .state import CaseState


class TraceLogger:
    """
    Persist full case traces to disk.

    The logger saves one JSON file per case and overwrites it after every step.
    This is simple, robust, and convenient for debugging and replay.
    """

    def __init__(self, trace_dir: str):
        """
        Args:
            trace_dir: Directory where trace JSON files will be stored.
        """
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self, state: CaseState) -> Dict[str, Any]:
        """
        Convert a CaseState object into a JSON-serializable dictionary.
        """
        return state.to_dict()

    def get_trace_path(self, state: CaseState) -> Path:
        """
        Get the file path for a case trace.

        Args:
            state: Current case state.

        Returns:
            Path to the trace file.
        """
        filename = f"{state.case_id}.json"
        return self.trace_dir / filename

    def save_case_state(self, state: CaseState) -> str:
        """
        Save the current case state to disk.

        This method overwrites the full trace file each time it is called.

        Args:
            state: The current case state.

        Returns:
            The trace file path as a string.
        """
        trace_path = self.get_trace_path(state)
        payload = self.to_dict(state)

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return str(trace_path)