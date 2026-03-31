# runtime/tool_executor.py

from __future__ import annotations

import time
from typing import Any, Dict

from tools.adapters import call_tool


class ToolExecutor:
    """
    Execute registered tools safely.

    This module is the only place where parsed tool actions are actually
    executed. It converts exceptions into structured error outputs so that
    the runtime never crashes because of a bad tool call.
    """

    def __init__(self, tool_registry: Dict[str, Any]):
        """
        Args:
            tool_registry: Mapping from tool name to tool object.
        """
        self.tool_registry = tool_registry

    def execute(self, action_name: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool action.

        Args:
            action_name: Name of the tool to invoke.
            action_input: Parsed JSON arguments for the tool.

        Returns:
            A structured result:
            {
                "success": bool,
                "observation": str | None,
                "error": str | None,
                "latency": float | None
            }
        """
        start_time = time.perf_counter()

        if not isinstance(action_name, str) or not action_name.strip():
            return {
                "success": False,
                "observation": None,
                "error": "Invalid tool name.",
                "latency": None,
            }

        if action_name not in self.tool_registry:
            return {
                "success": False,
                "observation": None,
                "error": f"Unknown tool: {action_name}",
                "latency": None,
            }

        tool = self.tool_registry[action_name]

        try:
            observation = call_tool(tool, action_input)
            latency = time.perf_counter() - start_time
            return {
                "success": True,
                "observation": observation,
                "error": None,
                "latency": latency,
            }
        except Exception as e:
            latency = time.perf_counter() - start_time
            return {
                "success": False,
                "observation": None,
                "error": f"Tool execution failed for {action_name}: {e}",
                "latency": latency,
            }