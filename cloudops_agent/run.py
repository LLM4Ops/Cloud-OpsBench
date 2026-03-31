from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# -------------------------------------------------------------------
# Make project root importable
# -------------------------------------------------------------------
AGENT_ROOT = Path(__file__).resolve().parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

# -------------------------------------------------------------------
# Project-local imports
# -------------------------------------------------------------------
from prompts.config_utils import load_config
from prompts.RCA_candidate import agent_prompt, build_expected_output
from prompts.prompt_optimization import get_cot_prompt, get_icl_prompt, get_rag_prompt
from tools.definition import create_k8s_tools
from tools.registry import build_tool_registry, render_tools_description

from runtime.state import init_case_state
from runtime.prompt_builder import PromptBuilder
from runtime.model_runner import ModelRunner
from runtime.output_parser import OutputParser
from runtime.tool_executor import ToolExecutor
from runtime.logger import TraceLogger
from runtime.agent_runtime import AgentRuntime

MAX_CASES_TO_RUN = 50
DEFAULT_DATASET_ROOT = Path("/root/k8srca/Cloud-OpsBench_history")
DEFAULT_SAVE_ROOT = Path("/root/whyfail")


def normalize_system_name(system: str) -> str:
    system_key = (system or "").strip().lower()
    if system_key in {"trainticket", "train-ticket"}:
        return "trainticket"
    if system_key == "boutique":
        return "boutique"
    raise ValueError(f"Unsupported system: {system}")


def resolve_workspace_path(diag_conf: Dict[str, Any], normalized_system: str) -> Path:
    configured = diag_conf.get("workspace_path")
    if configured:
        return Path(configured)

    dataset_root = Path(diag_conf.get("dataset_root", DEFAULT_DATASET_ROOT))
    return dataset_root / "benchmark" / normalized_system


def resolve_save_path(diag_conf: Dict[str, Any], normalized_system: str) -> Path:
    configured = diag_conf.get("save_path")
    if configured:
        return Path(configured)

    save_root = Path(diag_conf.get("save_root", DEFAULT_SAVE_ROOT))
    return save_root / normalized_system


def load_metadata(meta_path: Path) -> Dict[str, Any]:
    """Load metadata.json for one case."""
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt_backstory(
    prompt_strategy: str,
    workspace_path: str,
    fault_category: str,
    fault_path: str,
    system: str,
) -> str:
    """
    Build the system/backstory prompt according to the configured prompt strategy.
    """
    if prompt_strategy == "base":
        return agent_prompt
    elif prompt_strategy == "cot":
        return get_cot_prompt()
    elif prompt_strategy == "rag":
        return get_rag_prompt()
    elif prompt_strategy == "icl":
        normalized_system = normalize_system_name(system)
        workspace_root = Path(workspace_path)
        dataset_root = workspace_root.parent.parent
        demo_path = dataset_root / "golden-trajectory" / normalized_system / fault_category
        return get_icl_prompt(str(demo_path), fault_path)
    else:
        raise ValueError(f"Unknown prompt_strategy: {prompt_strategy}")


def build_model_runner(llm_conf: Dict[str, Any]) -> ModelRunner:
    """
    Construct ModelRunner from project config.
    """
    return ModelRunner(
        model_name=llm_conf["model"],
        provider="openai_compatible",
        api_base=llm_conf["api_base"],
        api_key=llm_conf["api_key"],
        temperature=llm_conf.get("temperature", 0.0),
        max_tokens=llm_conf.get("max_tokens", 1024),
        timeout=llm_conf.get("timeout"),
    )


def resolve_case_names(fault_root: Path, diag_conf: Dict[str, Any]) -> List[str]:
    """
    Resolve case names from config.

    Rules:
    - If config specifies a non-empty case_name, run only that case.
    - Otherwise, enumerate all subdirectories under fault_root.
    """
    case_name = diag_conf.get("case_name", None)

    if case_name is not None and str(case_name).strip():
        return [str(case_name).strip()]

    if not fault_root.exists():
        raise FileNotFoundError(f"Fault root not found: {fault_root}")

    case_names = sorted(
        p.name for p in fault_root.iterdir()
        if p.is_dir()
    )

    if not case_names:
        raise ValueError(f"No case directories found under: {fault_root}")

    return case_names


def run_single_case(
    case_name: str,
    workspace_path: str,
    save_path: str,
    fault_category: str,
    prompt_eng: str,
    model_name: str,
    max_iterations: int,
    llm_conf: Dict[str, Any],
    backstory_prompt: str,
) -> None:
    """
    Run one single case end-to-end.
    """
    # -------------------------------------------------------------------
    # 1. Resolve paths
    # -------------------------------------------------------------------
    # fault_root = Path(workspace_path) / "benchmark" / fault_category
    fault_root = Path(workspace_path)/ fault_category
    case_path = fault_root / case_name
    meta_path = case_path / "metadata.json"

    if not case_path.exists():
        raise FileNotFoundError(f"Case path not found: {case_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {meta_path}")

    diag_root = Path(save_path) / f"{model_name}_{prompt_eng}" / fault_category
    diag_case_path = diag_root / case_name
    diag_case_path.mkdir(parents=True, exist_ok=True)

    trace_dir = str(diag_case_path)
    result_path = diag_case_path / "result_raw.json"

    # If final result already exists, skip rerun
    if result_path.exists():
        print(f"[SKIP] Case already has result_raw.json: {case_name}")
        return

    # -------------------------------------------------------------------
    # 2. Load metadata
    # -------------------------------------------------------------------
    metadata_data = load_metadata(meta_path)
    query = metadata_data.get("query", "")
    namespace = metadata_data.get("namespace", "")
    result = metadata_data.get("result", "")

    # -------------------------------------------------------------------
    # 3. Build question
    # -------------------------------------------------------------------
    full_question = (
        f"The Kubernetes environment in namespace `{namespace}` is experiencing a fault. "
        f"A high-level symptom has been reported: '{query}'. "
        f"Diagnose the root cause of this incident."
    )

    # -------------------------------------------------------------------
    # 4. Initialize tools
    # -------------------------------------------------------------------
    benchmark_system = "train-ticket" if namespace == "train-ticket" else "boutique"
    tools_list = create_k8s_tools(str(case_path), system=benchmark_system)
    tool_registry = build_tool_registry(tools_list)
    tools_description = render_tools_description(tool_registry)

    # -------------------------------------------------------------------
    # 5. Initialize runtime components
    # -------------------------------------------------------------------
    prompt_builder = PromptBuilder(
        tools_description=tools_description,
        backstory_prompt=backstory_prompt,
        expected_output=build_expected_output(benchmark_system),
    )
    model_runner = build_model_runner(llm_conf)
    output_parser = OutputParser()
    tool_executor = ToolExecutor(tool_registry=tool_registry)
    trace_logger = TraceLogger(trace_dir=trace_dir)

    runtime = AgentRuntime(
        prompt_builder=prompt_builder,
        model_runner=model_runner,
        output_parser=output_parser,
        tool_executor=tool_executor,
        trace_logger=trace_logger,
    )

    # -------------------------------------------------------------------
    # 6. Initialize case state
    # -------------------------------------------------------------------
    state = init_case_state(
        case_id=case_name,
        system_name=fault_category,
        question=full_question,
        case_path=str(case_path),
        max_steps=max_iterations,
        ground_truth=result if isinstance(result, dict) else {"raw_result": result},
        metadata={
            "namespace": namespace,
            "query": query,
            "result": result,
            "fault_category": fault_category,
            "prompt_strategy": prompt_eng,
            "model_name": model_name,
        },
    )

    # -------------------------------------------------------------------
    # 7. Run one case
    # -------------------------------------------------------------------
    final_state = runtime.run_case(state)

    # -------------------------------------------------------------------
    # 8. Save final raw result
    # -------------------------------------------------------------------
    result_payload = {
        "Completed": str(final_state.final_answer or ""),
        "finished": final_state.finished,
        "stop_reason": final_state.stop_reason,
        "steps_used": len(final_state.history),
    }
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------
    # 9. Print summary
    # -------------------------------------------------------------------
    trace_path = trace_logger.get_trace_path(final_state)

    print("=" * 80)
    print("Cloud-OpsBench Single-Agent ReAct Runtime")
    print("=" * 80)
    print(f"Model         : {model_name}")
    print(f"Fault Category: {fault_category}")
    print(f"Prompt Strat. : {prompt_eng}")
    print(f"Case Name     : {case_name}")
    print(f"Case Path     : {case_path}")
    print(f"Finished      : {final_state.finished}")
    print(f"Stop Reason   : {final_state.stop_reason}")
    print(f"Steps Used    : {len(final_state.history)}")
    print(f"Trace Path    : {trace_path}")
    print(f"Result Path   : {result_path}")
    print("-" * 80)
    print("Final Answer:")
    print(final_state.final_answer or "[No final answer produced]")
    print("=" * 80)


def main() -> None:
    # -------------------------------------------------------------------
    # 1. Load config
    # -------------------------------------------------------------------
    config = load_config(str(AGENT_ROOT / "configs/model_configs.yaml"))
    llm_conf = config.model
    diag_conf = config.diagnosis

    model_name = llm_conf["model"]
    normalized_system = normalize_system_name(diag_conf["system"])
    workspace_path = resolve_workspace_path(diag_conf, normalized_system)
    save_path = resolve_save_path(diag_conf, normalized_system)
    fault_category = diag_conf["fault_category"]
    prompt_eng = diag_conf["prompt_strategy"]
    max_iterations = diag_conf["max_iterations"]
    system = normalized_system

    # fault_root = Path(workspace_path) / "benchmark" / fault_category
    fault_root = workspace_path / fault_category
    if not fault_root.exists():
        raise FileNotFoundError(f"Fault root not found: {fault_root}")

    # -------------------------------------------------------------------
    # 2. Build shared prompt backstory once
    # -------------------------------------------------------------------
    backstory_prompt = build_prompt_backstory(
        prompt_strategy=prompt_eng,
        workspace_path=str(workspace_path),
        fault_category=fault_category,
        fault_path=str(fault_root),
        system=system,
    )

    # -------------------------------------------------------------------
    # 3. Resolve case list
    # -------------------------------------------------------------------
    case_names = resolve_case_names(fault_root, diag_conf)
    # case_names = case_names[:MAX_CASES_TO_RUN]

    print("✅ Configuration loading completed")
    print(f"Model          : {model_name}")
    print(f"Fault category : {fault_category}")
    print(f"Prompt strategy: {prompt_eng}")
    print(f"Workspace path : {workspace_path}")
    print(f"Save path      : {save_path}")
    print(f"Max iterations : {max_iterations}")
    print(f"Max cases      : {MAX_CASES_TO_RUN}")
    print(f"Case count     : {len(case_names)}")
    print(f"Cases          : {case_names}")

    # -------------------------------------------------------------------
    # 4. Run all selected cases
    # -------------------------------------------------------------------
    for idx, case_name in enumerate(case_names, start=1):
        print(f"\n[RUN] ({idx}/{len(case_names)}) case={case_name}")
        try:
            run_single_case(
                case_name=case_name,
                workspace_path=str(workspace_path),
                save_path=str(save_path),
                fault_category=fault_category,
                prompt_eng=prompt_eng,
                model_name=model_name,
                max_iterations=max_iterations,
                llm_conf=llm_conf,
                backstory_prompt=backstory_prompt,
            )
        except Exception as e:
            print(f"[ERROR] case={case_name} failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        sys.exit(1)
