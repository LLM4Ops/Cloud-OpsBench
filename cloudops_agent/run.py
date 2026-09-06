from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "model_configs.yaml"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.context import ContextBuilder
from harness.harness import CloudOpsHarness
from runtime.contracts import build_expected_output
from runtime.core import OutputParser, ToolExecutor, TraceLogger, init_case_state, load_config
from runtime.llm import ModelRunner
from tools.cloudops import build_tool_registry, create_k8s_tools, render_tools_description


TOOL_SYSTEM = {"boutique": "boutique", "trainticket": "train-ticket"}
DEFAULT_NAMESPACE = {"boutique": "boutique", "trainticket": "train-ticket"}


def numeric_case_key(path: Path) -> tuple[int, str]:
    return (int(path.name), path.name) if path.name.isdigit() else (2**63 - 1, path.name)


def resolve_cases(config: Dict[str, Any]) -> list[Path]:
    diagnosis = config["diagnosis"]
    root = (
        Path(str(diagnosis["dataset_root"])).expanduser()
        / "benchmark"
        / diagnosis["system"]
        / str(diagnosis["fault_category"])
    )
    if not root.is_dir():
        raise FileNotFoundError(f"Fault category does not exist: {root}")
    case_name = str(diagnosis.get("case_name") or "").strip()
    if case_name:
        case = root / case_name
        if not case.is_dir():
            raise FileNotFoundError(f"Case does not exist: {case}")
        return [case]
    cases = sorted((path for path in root.iterdir() if path.is_dir()), key=numeric_case_key)
    if not cases:
        raise ValueError(f"No cases found in {root}")
    return cases


def build_model_runner(model: Dict[str, Any]) -> ModelRunner:
    enable_thinking = model.get("enable_thinking")
    return ModelRunner(
        model_name=str(model["model"]),
        provider=str(model.get("provider") or "openai_compatible"),
        api_base=str(model["api_base"]),
        api_key=str(model["api_key"]),
        temperature=float(model.get("temperature", 0)),
        max_tokens=int(model.get("max_tokens", 8192)),
        timeout=model.get("timeout"),
        enable_thinking=(
            bool(enable_thinking) if enable_thinking is not None else None
        ),
    )


def is_complete(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        trace = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return trace.get("stop_reason") in {"submit", "max_steps"}


def run_case(config: Dict[str, Any], case_path: Path, model_runner: ModelRunner) -> None:
    model = config["model"]
    diagnosis = config["diagnosis"]
    system = diagnosis["system"]
    category = str(diagnosis["fault_category"])
    case_id = case_path.name
    trace_dir = (
        Path(str(diagnosis["save_root"])).expanduser()
        / system
        / str(model["model"])
        / category
        / case_id
    )
    trace_path = trace_dir / f"{case_id}.json"
    if is_complete(trace_path):
        print(f"[SKIP] completed case={system}/{category}/{case_id}", flush=True)
        return

    metadata = json.loads((case_path / "metadata.json").read_text(encoding="utf-8"))
    namespace = str(metadata.get("namespace") or DEFAULT_NAMESPACE[system])
    query = str(metadata.get("query") or "")
    tool_system = TOOL_SYSTEM[system]
    registry = build_tool_registry(
        create_k8s_tools(str(case_path), system=tool_system, fault_category=category)
    )
    context = ContextBuilder(
        tools_description=render_tools_description(registry),
        expected_output=build_expected_output(tool_system),
    )
    state = init_case_state(
        case_id=case_id,
        system_name=system,
        question=(
            f"The Kubernetes environment in namespace `{namespace}` is experiencing a fault. "
            f"A high-level symptom has been reported: '{query}'. "
            "Diagnose the root cause of this incident."
        ),
        case_path=str(case_path),
        max_steps=int(diagnosis["max_iterations"]),
        metadata={
            "namespace": namespace,
            "query": query,
            "fault_category": category,
            "model_name": str(model["model"]),
        },
    )
    logger = TraceLogger(trace_dir)
    final = CloudOpsHarness(
        context_builder=context,
        model_runner=model_runner,
        output_parser=OutputParser(),
        tool_executor=ToolExecutor(registry),
        trace_logger=logger,
    ).run_case(state)
    (trace_dir / "result_raw.json").write_text(
        json.dumps(
            {
                "Completed": str(final.final_answer or ""),
                "finished": final.finished,
                "stop_reason": final.stop_reason,
                "steps_used": final.current_step,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"[DONE] case={system}/{category}/{case_id} finished={final.finished} "
        f"steps={final.current_step} trace={trace_path}",
        flush=True,
    )


def main() -> None:
    config = load_config(CONFIG_PATH)
    cases = resolve_cases(config)
    model_runner = build_model_runner(config["model"])
    diagnosis = config["diagnosis"]
    print(
        f"[PLAN] system={diagnosis['system']} category={diagnosis['fault_category']} "
        f"cases={len(cases)} model={config['model']['model']} "
        f"save_root={diagnosis['save_root']}",
        flush=True,
    )
    for index, case_path in enumerate(cases, 1):
        print(f"[RUN] {index}/{len(cases)} case={case_path.name}", flush=True)
        try:
            run_case(config, case_path, model_runner)
        except Exception as exc:
            print(f"[ERROR] case={case_path.name} {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
