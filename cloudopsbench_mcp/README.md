# Cloud-OpsBench MCP Server

Connect an MCP-compatible agent to a Cloud-OpsBench incident snapshot without
using the bundled ReAct agent. This package serves the existing diagnostic tools
through **Streamable HTTP** and supports both benchmark systems:

| System | Dataset directory | Server system setting | Tools |
| --- | --- | --- | ---: |
| Online Boutique | `benchmark/boutique/` | `boutique` | 12 |
| TrainTicket | `benchmark/trainticket/` | `train-ticket` | 10 |

Tool names, descriptions, argument schemas, and execution come directly from
`agents/cloudops_agent/tools/`. There is no separate MCP copy of the diagnostic
backend. The server requires no LLM API key, model configuration, or live cluster.

One server instance serves one case selected at startup. Clients discover its
tools using `tools/list` and call them using `tools/call`; they cannot select a
different case through a tool argument. The server does not expose MCP resources,
MCP prompts, Skills, or `SelectSymptom`.

## Installation

Use Python 3.10 or newer. Run these commands from the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r cloudopsbench_mcp/requirements.txt
```

The MCP requirements cover the diagnostic backend dependencies used here; an
OpenAI client package is not needed to run the server.

## Start a Boutique case

From the repository root:

```bash
export CLOUDOPSBENCH_CASE_PATH="$PWD/benchmark/boutique/runtime/1"
export CLOUDOPSBENCH_SYSTEM="boutique"
export CLOUDOPSBENCH_FAULT_CATEGORY="runtime"
export CLOUDOPSBENCH_RUN_ID="boutique-runtime-1"
export CLOUDOPSBENCH_TRACE_PATH="$PWD/.runs/boutique-runtime-1/mcp.jsonl"

.venv/bin/python -m cloudopsbench_mcp
```

Leave the server running while the agent diagnoses the case. Its endpoint is
`http://127.0.0.1:8000/mcp`. Stop it with Ctrl-C before starting another case.
For a code-defect case, select its `benchmark/boutique/codedefect/<id>` directory
and set `CLOUDOPSBENCH_FAULT_CATEGORY="codedefect"`.

## Start a TrainTicket case

From the repository root:

```bash
export CLOUDOPSBENCH_CASE_PATH="$PWD/benchmark/trainticket/service/25"
export CLOUDOPSBENCH_SYSTEM="train-ticket"
export CLOUDOPSBENCH_FAULT_CATEGORY="service"
export CLOUDOPSBENCH_RUN_ID="trainticket-service-25"
export CLOUDOPSBENCH_TRACE_PATH="$PWD/.runs/trainticket-service-25/mcp.jsonl"

.venv/bin/python -m cloudopsbench_mcp
```

The directory is named **`trainticket`**, while the diagnostic backend setting is
**`train-ticket`**. The client configuration is identical for both systems; the
server supplies the appropriate catalog and tool descriptions.

If a client cannot connect despite the server being ready, check that its HTTP
proxy excludes `127.0.0.1` and `localhost`. Local MCP traffic must go directly to
the loopback server, not through a proxy.

## Connect an agent

Start the server first, then follow one of the minimal client examples:

- [Codex](examples/codex/README.md), with a `config.toml` snippet.
- [OpenCode](examples/opencode/README.md), with an `opencode.json` example.

Configure the task model and credentials in the client. The examples contain no
API credentials, model-specific settings, or evolved diagnostic knowledge.
Use a separate agent workspace and supply the incident's `query` and `namespace`
from `metadata.json` as the task description. Its ground-truth `result` field is
for the evaluator, not the agent. For example:

```text
Diagnose the reported incident in namespace <namespace>.
Incident report: <query>
Use the cloudopsbench MCP tools to collect incident evidence.
Identify the faulty component and root cause, and explain the supporting evidence.
```

This is a connection example, not a full batch-evaluation runner. The client
owns reasoning and final-answer generation; the server supplies tool results.
An evaluator must separately capture the client's final diagnosis. The MCP
JSONL trace alone is not the bundled agent's evaluation input format.

## Tool catalog

Both systems expose these ten tools:

```text
GetResources                 DescribeResource
GetAppYAML                   GetRecentLogs
GetErrorLogs                 CheckServiceConnectivity
GetServiceDependencies       GetClusterConfiguration
GetAlerts                    CheckNodeServiceStatus
```

Boutique additionally exposes `ListCodeFiles` and `GetSourceCode`. TrainTicket
does not have source-code tools. Argument schemas follow the selected backend,
including the extended `GetResources` schema for Boutique code-defect cases.
Clients should discover schemas rather than hard-code one across all cases.

## Server configuration

Configuration is supplied by the trusted launcher through environment variables:

| Variable | Required / default | Meaning |
| --- | --- | --- |
| `CLOUDOPSBENCH_CASE_PATH` | Required | Active case directory or restricted snapshot view |
| `CLOUDOPSBENCH_FAULT_CATEGORY` | Required | Case category; preserves native tool-schema selection |
| `CLOUDOPSBENCH_SYSTEM` | `boutique` | `boutique` or `train-ticket` |
| `CLOUDOPSBENCH_MCP_HOST` | `127.0.0.1` | Bind address |
| `CLOUDOPSBENCH_MCP_PORT` | `8000` | HTTP port |
| `CLOUDOPSBENCH_RUN_ID` | Generated UUID | Run identifier in the trace |
| `CLOUDOPSBENCH_TRACE_PATH` | `/tmp/cloudopsbench-mcp-trajectory.jsonl` | Append-only JSONL trace path |
| `CLOUDOPSBENCH_MAX_TOOL_CALLS` | Unset: unlimited | Optional positive limit on admitted tool requests |

For concurrent cases, use a separate server instance, port, run ID, and trace
file for each case. Restart the server and the agent session when changing cases.

By default, there is no tool-call limit. If a launcher sets
`CLOUDOPSBENCH_MAX_TOOL_CALLS`, requests beyond the limit return an MCP tool error
without executing the backend. Admitted invalid requests count toward the limit.
The server does not terminate the client or declare a diagnosis incorrect;
evaluation runners define their own stopping and scoring policies.

## Tool-call traces

Each admitted request is appended to the trace with `run_id`, `sequence`, UTC
`timestamp`, `tool_name`, validated `arguments` (original arguments on validation
errors), complete `output`, `is_error`, and `duration_ms`. Rejected over-budget
requests do not execute the backend and are not appended. Use a fresh trace file
per run; reusing a path appends to the existing log.

Adapter errors are returned with MCP `isError=true`. Native backend messages,
including errors already represented as text by the original tools, are
preserved rather than reinterpreted as new diagnostic judgments.

## Benchmark data boundary

The local commands above help check integration. For isolated benchmark runs,
the launcher should expose only the active snapshot files to the server:

- `tool_cache.json`
- `raw_data/`
- `code/` when present (Boutique)

Keep `metadata.json`, `process-label/`, and `golden-trajectory/` outside that
snapshot view. Keep benchmark files, labels, and server traces outside the agent
workspace. The MCP interface does not itself sandbox the client's filesystem;
the benchmark runner or container configuration provides that isolation.

## Offline checks

From the repository root:

```bash
.venv/bin/python -m unittest discover -s cloudopsbench_mcp/tests -v
```

Tests check both systems' catalogs, backend-equivalent results, argument
validation, optional request limits, restricted snapshot access, and real
loopback HTTP connections. They require the repository snapshots and make no
LLM or external network calls.
