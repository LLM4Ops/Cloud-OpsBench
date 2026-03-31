# runtime/output_parser.py

from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, Optional


class OutputParser:
    """
    Parse model outputs into one of two structured forms:

    1) Tool call format
       Thought: ...
       Action: <tool_name>
       Action Input: <json object>

    2) Final diagnosis JSON output
       {
         ...
       }

    If parsing fails, return type="invalid" with an error message.
    """

    THOUGHT_PATTERN = re.compile(
        r"Thought:\s*(.*?)(?=\n(?:Action:|Action Input:)|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    ACTION_PATTERN = re.compile(
        r"Action:\s*(.+?)(?=\nAction Input:|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    ACTION_INPUT_PATTERN = re.compile(
        r"Action Input:\s*(\{.*\})\s*$",
        re.DOTALL | re.IGNORECASE,
    )

    JSON_BLOCK_PATTERN = re.compile(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        re.DOTALL | re.IGNORECASE,
    )

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse raw model output.

        Returns:
            Tool action:
            {
                "type": "tool",
                "thought": str | None,
                "action_name": str,
                "action_input": dict,
                "final_answer": None,
                "final_json": None,
                "error": None,
            }

            Final JSON:
            {
                "type": "finish",
                "thought": None,
                "action_name": None,
                "action_input": None,
                "final_answer": str,   # serialized JSON string
                "final_json": dict,    # parsed dict
                "error": None,
            }

            Invalid:
            {
                "type": "invalid",
                ...
                "error": str,
            }
        """
        safe_text = text if isinstance(text, str) else str(text)
        stripped = safe_text.strip()

        # 1. First try tool-call parsing
        tool_result = self._parse_tool_call(stripped)
        if tool_result["type"] == "tool":
            return tool_result

        # 2. Then try final JSON parsing
        json_result = self._parse_final_json(stripped)
        if json_result["type"] == "finish":
            return json_result

        # 3. If neither worked, return invalid
        combined_error = self._combine_errors(
            tool_result.get("error"),
            json_result.get("error"),
        )

        return {
            "type": "invalid",
            "thought": tool_result.get("thought"),
            "action_name": None,
            "action_input": None,
            "final_answer": None,
            "final_json": None,
            "error": combined_error or "Could not parse either a tool call or a final JSON output.",
        }

    def _parse_tool_call(self, text: str) -> Dict[str, Any]:
        """
        Try to parse tool-call format.
        """
        thought = self._extract_thought(text)
        action_name = self._extract_action_name(text)
        action_input_text = self._extract_action_input_text(text)

        if action_name is None and action_input_text is None:
            return {
                "type": "invalid",
                "thought": thought,
                "action_name": None,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "No Action / Action Input block found.",
            }

        if action_name is None:
            return {
                "type": "invalid",
                "thought": thought,
                "action_name": None,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "Found Action Input but missing Action.",
            }

        if action_input_text is None:
            return {
                "type": "invalid",
                "thought": thought,
                "action_name": action_name,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "Found Action but missing or malformed Action Input.",
            }

        parsed_input, parse_error = self._safe_parse_json(action_input_text)
        if parse_error is not None:
            return {
                "type": "invalid",
                "thought": thought,
                "action_name": action_name,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": f"Failed to parse Action Input JSON: {parse_error}",
            }

        if not isinstance(parsed_input, dict):
            return {
                "type": "invalid",
                "thought": thought,
                "action_name": action_name,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "Action Input must be a JSON object.",
            }

        return {
            "type": "tool",
            "thought": thought,
            "action_name": action_name,
            "action_input": parsed_input,
            "final_answer": None,
            "final_json": None,
            "error": None,
        }

    def _parse_final_json(self, text: str) -> Dict[str, Any]:
        """
        Try to parse final output as strict JSON.

        This supports the new expected_output design where the final response
        must be pure JSON with no extra text.
        """
        normalized_text = self._extract_final_json_text(text)
        json_obj, error = self._safe_parse_json(normalized_text)
        if error is not None:
            return {
                "type": "invalid",
                "thought": None,
                "action_name": None,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": f"Final JSON parse failed: {error}",
            }

        if not isinstance(json_obj, dict):
            return {
                "type": "invalid",
                "thought": None,
                "action_name": None,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "Final output JSON must be a JSON object.",
            }

        # Minimal sanity check
        if "top_3_predictions" not in json_obj:
            return {
                "type": "invalid",
                "thought": None,
                "action_name": None,
                "action_input": None,
                "final_answer": None,
                "final_json": None,
                "error": "Final JSON missing required key: top_3_predictions",
            }

        # Keep both parsed dict and serialized form
        return {
            "type": "finish",
            "thought": None,
            "action_name": None,
            "action_input": None,
            "final_answer": json.dumps(json_obj, ensure_ascii=False),
            "final_json": json_obj,
            "error": None,
        }

    def _extract_final_json_text(self, text: str) -> str:
        """
        Normalize common final-answer formats into a raw JSON string.

        Supported forms:
        - pure JSON object
        - fenced JSON block: ```json { ... } ```
        - Thought: ... followed by a fenced JSON block
        - Thought: ... followed by a raw JSON object
        """
        stripped = text.strip()

        fence_match = self.JSON_BLOCK_PATTERN.search(stripped)
        if fence_match:
            return fence_match.group(1).strip()

        json_start = stripped.find("{")
        json_end = stripped.rfind("}")
        if json_start != -1 and json_end != -1 and json_start < json_end:
            candidate = stripped[json_start : json_end + 1].strip()
            if candidate:
                return candidate

        return stripped

    def _extract_thought(self, text: str) -> Optional[str]:
        """
        Extract Thought block if present.
        """
        normalized_text = self.JSON_BLOCK_PATTERN.sub("", text)
        match = self.THOUGHT_PATTERN.search(normalized_text)
        if not match:
            return None
        thought = match.group(1).strip()
        return thought or None

    def _extract_action_name(self, text: str) -> Optional[str]:
        """
        Extract Action name if present.
        """
        match = self.ACTION_PATTERN.search(text)
        if not match:
            return None
        action_name = match.group(1).strip()
        return action_name or None

    def _extract_action_input_text(self, text: str) -> Optional[str]:
        """
        Extract Action Input JSON string if present.
        """
        match = self.ACTION_INPUT_PATTERN.search(text)
        if not match:
            return None
        action_input_text = match.group(1).strip()
        return action_input_text or None

    def _safe_parse_json(self, text: str) -> tuple[Optional[Any], Optional[str]]:
        """
        Safely parse JSON and return (value, error_message).

        Never raises.
        """
        try:
            return json.loads(text), None
        except Exception as json_error:
            repaired_text = self._repair_near_json(text)

            if repaired_text != text:
                try:
                    return json.loads(repaired_text), None
                except Exception:
                    pass

            try:
                return ast.literal_eval(text), None
            except Exception:
                pass

            if repaired_text != text:
                try:
                    return ast.literal_eval(repaired_text), None
                except Exception:
                    pass

            return None, str(json_error)

    def _repair_near_json(self, text: str) -> str:
        """
        Repair common near-JSON outputs produced by LLMs.

        Examples:
        - None -> null
        - True -> true
        - False -> false
        """
        repaired = re.sub(r"\bNone\b", "null", text)
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        return repaired

    def _combine_errors(self, tool_error: Optional[str], json_error: Optional[str]) -> str:
        """
        Combine parser errors into one message.
        """
        errors = []
        if tool_error:
            errors.append(f"Tool parse error: {tool_error}")
        if json_error:
            errors.append(f"Final JSON parse error: {json_error}")
        return " | ".join(errors)
