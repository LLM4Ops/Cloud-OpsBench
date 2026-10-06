from __future__ import annotations

import asyncio
import json
import shutil
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import uvicorn
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from cloudopsbench_mcp.server import CloudOpsMCP, ServerSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TOOLS = [
    "GetResources",
    "DescribeResource",
    "GetAppYAML",
    "GetRecentLogs",
    "GetErrorLogs",
    "CheckServiceConnectivity",
    "GetServiceDependencies",
    "GetClusterConfiguration",
    "GetAlerts",
    "CheckNodeServiceStatus",
    "ListCodeFiles",
    "GetSourceCode",
]


def boutique_case() -> Path:
    return REPO_ROOT / "benchmark" / "boutique" / "runtime" / "1"


class CloudOpsMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.trace_path = Path(self.temp_dir.name) / "trajectory.jsonl"
        case_path = boutique_case()
        self.adapter = CloudOpsMCP(
            ServerSettings(
                case_path=case_path,
                fault_category=case_path.parent.name,
                trace_path=self.trace_path,
                run_id="test-run",
            )
        )

    async def test_exposes_exactly_the_backend_twelve_tools(self) -> None:
        async with Client(self.adapter.server) as client:
            result = await client.list_tools()

        self.assertEqual([tool.name for tool in result.tools], EXPECTED_TOOLS)
        for tool in result.tools:
            self.assertNotIn("case_id", tool.input_schema.get("properties", {}))
            self.assertNotIn("case_path", tool.input_schema.get("properties", {}))
            self.assertFalse(tool.input_schema["additionalProperties"])

    async def test_call_result_matches_existing_backend(self) -> None:
        expected = self.adapter.registry["GetAlerts"]._run()
        async with Client(self.adapter.server) as client:
            result = await client.call_tool("GetAlerts", {})

        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0].text, expected)

    async def test_rejects_hidden_case_arguments_and_records_call(self) -> None:
        async with Client(self.adapter.server) as client:
            result = await client.call_tool("GetAlerts", {"case_id": "1"})

        self.assertTrue(result.is_error)
        event = json.loads(self.trace_path.read_text(encoding="utf-8").strip())
        self.assertEqual(event["run_id"], "test-run")
        self.assertEqual(event["tool_name"], "GetAlerts")
        self.assertEqual(event["arguments"], {"case_id": "1"})
        self.assertTrue(event["is_error"])

    async def test_trainticket_uses_its_backend_and_exposes_ten_tools(self) -> None:
        case_path = REPO_ROOT / "benchmark" / "trainticket" / "service" / "25"
        adapter = CloudOpsMCP(
            ServerSettings(
                case_path=case_path,
                fault_category="service",
                trace_path=self.trace_path,
                run_id="trainticket-test",
                system="train-ticket",
            )
        )
        async with Client(adapter.server) as client:
            listed = await client.list_tools()
            result = await client.call_tool("GetAlerts", {})

        self.assertEqual([tool.name for tool in listed.tools], EXPECTED_TOOLS[:-2])
        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0].text, str(adapter.registry["GetAlerts"]._run()))

    def make_adapter(self, system: str, category: str, case_id: str) -> CloudOpsMCP:
        directory = "trainticket" if system == "train-ticket" else system
        return CloudOpsMCP(
            ServerSettings(
                case_path=REPO_ROOT / "benchmark" / directory / category / case_id,
                fault_category=category,
                trace_path=self.trace_path,
                run_id=f"test-{directory}-{category}-{case_id}",
                system=system,
            )
        )

    async def test_catalog_preserves_backend_descriptions_and_schemas(self) -> None:
        for system, category, case_id in [
            ("boutique", "runtime", "1"),
            ("boutique", "codedefect", "1"),
            ("train-ticket", "service", "25"),
        ]:
            with self.subTest(system=system, category=category):
                adapter = self.make_adapter(system, category, case_id)
                async with Client(adapter.server) as client:
                    result = await client.list_tools()
                for exposed in result.tools:
                    native = adapter.registry[exposed.name]
                    expected = (
                        native.args_schema.model_json_schema()
                        if native.args_schema else {"type": "object", "properties": {}}
                    )
                    expected["additionalProperties"] = False
                    self.assertEqual(exposed.description, native.description)
                    self.assertEqual(exposed.input_schema, expected)
                    self.assertNotIn("case_id", exposed.input_schema.get("properties", {}))
                    self.assertNotIn("case_path", exposed.input_schema.get("properties", {}))

    async def test_resource_queries_match_both_backends(self) -> None:
        for system, category, case_id in [
            ("boutique", "runtime", "1"),
            ("train-ticket", "service", "25"),
        ]:
            with self.subTest(system=system):
                adapter = self.make_adapter(system, category, case_id)
                arguments = {"resource_type": "pods", "namespace": system}
                expected = adapter.registry["GetResources"]._run(**arguments)
                async with Client(adapter.server) as client:
                    result = await client.call_tool("GetResources", arguments)
                self.assertFalse(result.is_error)
                self.assertEqual(result.content[0].text, expected)

    async def test_boutique_source_code_matches_backend(self) -> None:
        adapter = self.make_adapter("boutique", "codedefect", "1")
        cache = json.loads((adapter.settings.case_path / "tool_cache.json").read_text())
        listing_key = next(
            key for key, value in cache.items()
            if key.startswith("ListCodeFiles:")
            and isinstance(value, dict) and value.get("files")
        )
        arguments = json.loads(listing_key.split(":", 1)[1])
        app_name = arguments["app_name"]
        file_path = cache[listing_key]["files"][0]["path"]
        source_arguments = {"app_name": app_name, "file_path": file_path}
        expected = adapter.registry["GetSourceCode"]._run(**source_arguments)
        self.assertFalse(expected.startswith("Error:"))
        async with Client(adapter.server) as client:
            listing = await client.call_tool("ListCodeFiles", arguments)
            source = await client.call_tool("GetSourceCode", source_arguments)
        self.assertFalse(listing.is_error)
        self.assertFalse(source.is_error)
        self.assertEqual(json.loads(listing.content[0].text), cache[listing_key])
        self.assertEqual(source.content[0].text, expected)

    async def test_missing_required_arguments_return_recorded_error(self) -> None:
        async with Client(self.adapter.server) as client:
            result = await client.call_tool("GetResources", {})
        self.assertTrue(result.is_error)
        event = json.loads(self.trace_path.read_text().strip())
        self.assertTrue(event["is_error"])
        self.assertEqual(event["arguments"], {})
        self.assertEqual(event["sequence"], 1)

    async def test_optional_limit_counts_invalid_requests_and_blocks_backend(self) -> None:
        adapter = CloudOpsMCP(replace(self.adapter.settings, max_tool_calls=2))
        async with Client(adapter.server) as client:
            first = await client.call_tool("GetAlerts", {})
            invalid = await client.call_tool("GetResources", {})
            blocked = await client.call_tool("GetAlerts", {})
        self.assertFalse(first.is_error)
        self.assertTrue(invalid.is_error)
        self.assertTrue(blocked.is_error)
        self.assertIn("limit reached", blocked.content[0].text)
        events = [json.loads(line) for line in self.trace_path.read_text().splitlines()]
        self.assertEqual([event["sequence"] for event in events], [1, 2])
        self.assertEqual([event["tool_name"] for event in events], ["GetAlerts", "GetResources"])

    async def test_restricted_snapshot_needs_no_metadata_or_labels(self) -> None:
        view = Path(self.temp_dir.name) / "snapshot"
        view.mkdir()
        shutil.copyfile(self.adapter.settings.case_path / "tool_cache.json", view / "tool_cache.json")
        # Raw logs are an optional backend input; only copy that incident file.
        logs = self.adapter.settings.case_path / "raw_data" / "logs.json"
        if logs.is_file():
            (view / "raw_data").mkdir()
            shutil.copyfile(logs, view / "raw_data" / "logs.json")
        adapter = CloudOpsMCP(replace(self.adapter.settings, case_path=view))
        expected = self.adapter.registry["GetAlerts"]._run()
        async with Client(adapter.server) as client:
            result = await client.call_tool("GetAlerts", {})
        self.assertFalse((view / "metadata.json").exists())
        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0].text, expected)

    async def check_http(self, system: str, category: str, case_id: str) -> None:
        adapter = self.make_adapter(system, category, case_id)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        self.addCleanup(listener.close)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            adapter.http_app(), host="127.0.0.1", port=port,
            log_level="critical", lifespan="on",
        ))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async def wait_ready():
                while not server.started:
                    if task.done():
                        await task
                        self.fail("HTTP server exited before becoming ready")
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(wait_ready(), timeout=5)
            # Loopback checks must not use machine-level HTTP proxy settings.
            async with httpx2.AsyncClient(trust_env=False) as http_client:
                transport = streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp", http_client=http_client,
                )
                async with Client(transport) as client:
                    catalog = await client.list_tools()
                    result = await client.call_tool("GetAlerts", {})
            expected_names = EXPECTED_TOOLS if system == "boutique" else EXPECTED_TOOLS[:-2]
            self.assertEqual([tool.name for tool in catalog.tools], expected_names)
            self.assertFalse(result.is_error)
            self.assertEqual(result.content[0].text, str(adapter.registry["GetAlerts"]._run()))
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=5)

    async def test_boutique_streamable_http_connection(self) -> None:
        await self.check_http("boutique", "runtime", "1")

    async def test_trainticket_streamable_http_connection(self) -> None:
        await self.check_http("train-ticket", "service", "25")


if __name__ == "__main__":
    unittest.main()
