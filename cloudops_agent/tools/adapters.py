from __future__ import annotations

import inspect
from typing import Any, Dict


def call_tool(tool: Any, action_input: Dict[str, Any]) -> str:
    if not hasattr(tool, "_run"):
        raise ValueError(f"Tool {tool} does not implement '_run'.")

    if action_input is None:
        action_input = {}

    if not isinstance(action_input, dict):
        raise ValueError("Tool action_input must be a dictionary.")

    filtered_input = action_input

    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None and hasattr(args_schema, "model_fields"):
        allowed_keys = set(args_schema.model_fields.keys())
        filtered_input = {k: v for k, v in action_input.items() if k in allowed_keys}
    else:
        signature = inspect.signature(tool._run)
        if not any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        ):
            allowed_keys = {
                name for name in signature.parameters.keys() if name != "self"
            }
            filtered_input = {k: v for k, v in action_input.items() if k in allowed_keys}

    result = tool._run(**filtered_input)

    if result is None:
        return ""

    if isinstance(result, str):
        return result

    return str(result)
