from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from mcp import types
from mcp.server.lowlevel import Server
from pydantic import ValidationError

from agents.cloudops_agent.tools.cloudops import (
    build_tool_registry,
    create_k8s_tools,
)

SERVER_NAME = "cloudopsbench"
SERVER_VERSION = "0.1.0"
EXPECTED_TOOL_COUNTS = {"boutique": 12, "train-ticket": 10}


@dataclass(frozen=True)
class ServerSettings:
    """Trusted, per-run configuration supplied by the benchmark runner."""

    case_path: Path
    fault_category: str
    trace_path: Path
    run_id: str
    system: str = "boutique"
    host: str = "127.0.0.1"
    port: int = 8000
    max_tool_calls: int | None = None

    @classmethod
    def from_env(cls) -> ServerSettings:
        case_path = os.environ.get("CLOUDOPSBENCH_CASE_PATH", "").strip()
        fault_category = os.environ.get("CLOUDOPSBENCH_FAULT_CATEGORY", "").strip()
        if not case_path:
            raise ValueError("CLOUDOPSBENCH_CASE_PATH is required")
        if not fault_category:
            raise ValueError("CLOUDOPSBENCH_FAULT_CATEGORY is required")
        system = os.environ.get("CLOUDOPSBENCH_SYSTEM", "boutique").strip()
        if system not in {"boutique", "train-ticket"}:
            raise ValueError("CLOUDOPSBENCH_SYSTEM must be boutique or train-ticket")
        call_limit = os.environ.get("CLOUDOPSBENCH_MAX_TOOL_CALLS", "").strip()
        max_tool_calls = int(call_limit) if call_limit else None
        if max_tool_calls is not None and max_tool_calls < 1:
            raise ValueError("CLOUDOPSBENCH_MAX_TOOL_CALLS must be positive")

        return cls(
            case_path=Path(case_path).expanduser().resolve(),
            fault_category=fault_category,
            trace_path=Path(
                os.environ.get(
                    "CLOUDOPSBENCH_TRACE_PATH",
                    "/tmp/cloudopsbench-mcp-trajectory.jsonl",
                )
            ).expanduser(),
            run_id=os.environ.get("CLOUDOPSBENCH_RUN_ID", "").strip()
            or str(uuid.uuid4()),
            system=system,
            host=os.environ.get("CLOUDOPSBENCH_MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("CLOUDOPSBENCH_MCP_PORT", "8000")),
            max_tool_calls=max_tool_calls,
        )


class TrajectoryRecorder:
    """Append-only JSONL audit log for MCP diagnostic tool calls."""

    def __init__(self, path: Path, run_id: str):
        self.path = path
        self.run_id = run_id
        self._sequence = 0
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        output: str,
        is_error: bool,
        duration_ms: float,
    ) -> None:
        with self._lock:
            self._sequence += 1
            event = {
                "run_id": self.run_id,
                "sequence": self._sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "arguments": arguments,
                "output": output,
                "is_error": is_error,
                "duration_ms": round(duration_ms, 3),
            }
            with self.path.open("a", encoding="utf-8") as trace_file:
                trace_file.write(json.dumps(event, ensure_ascii=False) + "\n")


class CloudOpsMCP:
    """Thin MCP protocol adapter over the existing CloudOpsBench tool registry."""

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self._admitted_calls = 0
        self._budget_lock = threading.Lock()
        tools = create_k8s_tools(
            str(settings.case_path),
            system=settings.system,
            fault_category=settings.fault_category,
        )
        self.registry = build_tool_registry(tools)
        expected_tool_count = EXPECTED_TOOL_COUNTS[settings.system]
        if len(self.registry) != expected_tool_count:
            raise RuntimeError(
                f"{settings.system} MCP requires exactly {expected_tool_count} tools; "
                f"backend returned {len(self.registry)}"
            )

        self.recorder = TrajectoryRecorder(settings.trace_path, settings.run_id)
        self.server = Server(
            SERVER_NAME,
            version=SERVER_VERSION,
            instructions=(
                "Diagnose the one preselected CloudOpsBench incident using these "
                "read-only tools. The benchmark runner selects the active snapshot; "
                "never request or provide a case ID or snapshot path."
            ),
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )

    async def _list_tools(self, _ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[self._to_mcp_tool(tool) for tool in self.registry.values()]
        )

    async def _call_tool(
        self, _ctx: Any, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        # Reserve slots before backend execution so parallel requests cannot
        # exceed the optional limit. Client termination remains the runner's job.
        with self._budget_lock:
            if (
                self.settings.max_tool_calls is not None
                and self._admitted_calls >= self.settings.max_tool_calls
            ):
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text="Run tool-call limit reached.")],
                    isError=True,
                )
            self._admitted_calls += 1
        started = time.perf_counter()
        arguments = dict(params.arguments or {})

        if params.name not in self.registry:
            return self._error_result(
                params.name,
                arguments,
                f"Unknown diagnostic tool: {params.name}",
                started,
            )

        tool = self.registry[params.name]
        try:
            validated_arguments = self._validate_arguments(tool, arguments)
            output = tool._run(**validated_arguments)
            output_text = "" if output is None else str(output)
        except (TypeError, ValueError, ValidationError) as exc:
            return self._error_result(
                params.name,
                arguments,
                f"Invalid tool arguments: {exc}",
                started,
            )
        # Backend tools intentionally convert operational failures into text. Keep
        # the MCP boundary equally defensive so clients receive a tool error rather
        # than an opaque JSON-RPC failure if a backend exception escapes.
        except Exception as exc:  # noqa: BLE001
            return self._error_result(
                params.name,
                arguments,
                f"Tool execution failed: {exc}",
                started,
            )

        duration_ms = (time.perf_counter() - started) * 1000
        self.recorder.record(
            tool_name=params.name,
            arguments=validated_arguments,
            output=output_text,
            is_error=False,
            duration_ms=duration_ms,
        )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=output_text)]
        )

    def _error_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        message: str,
        started: float,
    ) -> types.CallToolResult:
        self.recorder.record(
            tool_name=tool_name,
            arguments=arguments,
            output=message,
            is_error=True,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=message)],
            isError=True,
        )

    @staticmethod
    def _validate_arguments(tool: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        schema = getattr(tool, "args_schema", None)
        if schema is None:
            if arguments:
                raise ValueError("this tool takes no arguments")
            return {}

        allowed = set(schema.model_fields)
        unexpected = sorted(set(arguments) - allowed)
        if unexpected:
            raise ValueError(f"unexpected argument(s): {', '.join(unexpected)}")
        return schema.model_validate(arguments).model_dump()

    @staticmethod
    def _to_mcp_tool(tool: Any) -> types.Tool:
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            input_schema: dict[str, Any] = {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        else:
            input_schema = args_schema.model_json_schema()
            input_schema["additionalProperties"] = False

        return types.Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=input_schema,
            annotations=types.ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )

    def http_app(self):
        return self.server.streamable_http_app(
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            host=self.settings.host,
        )


def main() -> None:
    settings = ServerSettings.from_env()
    adapter = CloudOpsMCP(settings)
    uvicorn.run(adapter.http_app(), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
