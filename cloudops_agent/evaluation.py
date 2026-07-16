#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "model_configs.yaml"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

METRIC_DISPLAY_NAMES = {
    "CA": "Component Accuracy",
    "FA": "Fault-Type Accuracy",
    "JRA": "Joint RCA Accuracy",
    "MC": "Milestone Coverage",
    "EOC": "Evidence-Order Consistency",
    "ECR": "Evidence Closure Rate",
    "EE": "Evidence Efficiency",
    "steps": "Average Diagnostic Steps per Case",
    "RAR": "Redundant Action Rate",
    "invalid_actions": "Average Invalid Actions per Case",
}

from diagnostic_evidence.evaluator import evaluate_trajectory  # noqa: E402
from diagnostic_evidence.schema import CaseAnnotation, ToolCall, TrajectoryStep  # noqa: E402


def normalize_system_name(system: str) -> str:
    system_key = str(system or "").strip().lower()
    if system_key in {"trainticket", "train-ticket"}:
        return "trainticket"
    if system_key == "boutique":
        return "boutique"
    raise ValueError(f"Unsupported system: {system}")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_agent_case_for_evaluation(path: Path) -> Dict[str, Any]:
    """Load only fields needed by this evaluator.

    The stored agent traces can contain very large prompts/raw model outputs.
    json.loads must still parse the file, but this function immediately drops
    those bulky fields so downstream detail files and in-memory summaries stay
    small.
    """

    data = read_json(path)
    slim_steps = []
    for step in data.get("steps", []) or []:
        slim_steps.append(
            {
                "step_id": step.get("step_id"),
                "action_type": step.get("action_type"),
                "action_name": step.get("action_name"),
                "action_input": step.get("action_input"),
                "final_answer": step.get("final_answer"),
                "observation": step.get("observation"),
                "error": step.get("error"),
            }
        )
    return {
        "final_answer": data.get("final_answer"),
        "steps": slim_steps,
    }


def parse_json_maybe(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for pattern in (r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()
            break
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_final_answer_payload(case_data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    candidates: List[Tuple[str, Any]] = [("top_level_final_answer", case_data.get("final_answer"))]
    for step in reversed(case_data.get("steps", []) or []):
        if step.get("final_answer"):
            candidates.append((f"step_{step.get('step_id', 'unknown')}_final_answer", step.get("final_answer")))

    for source, candidate in candidates:
        parsed = parse_json_maybe(candidate)
        if parsed and isinstance(parsed.get("top_3_predictions"), list):
            return parsed, source
    return None, "unparsed"


def _parse_scalar(raw: str) -> Any:
    value = raw.split("#", 1)[0].strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def load_simple_yaml_config(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    section: Optional[str] = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.rstrip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1].strip()
            result[section] = {}
            continue
        if indent == 2 and section and ":" in line:
            key, value = line.strip().split(":", 1)
            result[section][key.strip()] = _parse_scalar(value)
    return result


def load_eval_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    if yaml is not None:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        config = load_simple_yaml_config(CONFIG_PATH)
    if not isinstance(config, dict):
        raise ValueError("Invalid config format: expected top-level mapping")
    return config


def resolve_case_names_from_split(
    diag_conf: Dict[str, Any],
    normalized_system: str,
    fault_category: str,
) -> Optional[List[str]]:
    split_name = str(diag_conf.get("case_split", "") or "").strip().lower()
    split_file = str(diag_conf.get("case_split_file", "") or "").strip()
    if not split_name:
        return None
    if split_name not in {"train", "test"}:
        raise ValueError("`diagnosis.case_split` must be either `train` or `test`")
    if not split_file:
        raise ValueError("`diagnosis.case_split_file` is required when `diagnosis.case_split` is set")

    split_path = Path(split_file).expanduser()
    if not split_path.exists():
        raise FileNotFoundError(f"Case split file not found: {split_path}")

    split_data = read_json(split_path)
    case_names: List[str] = []
    for split_entry in split_data.get("splits", []) or []:
        entry_system = split_entry.get("system", "")
        if normalize_system_name(entry_system) != normalized_system:
            continue
        for case_identifier in split_entry.get(split_name, []) or []:
            parts = str(case_identifier).strip().split("/")
            if len(parts) != 3:
                continue
            raw_system, raw_fault_category, case_name = parts
            if normalize_system_name(raw_system) != normalized_system:
                continue
            if raw_fault_category == fault_category and case_name:
                case_names.append(case_name)

    case_names = sorted(set(case_names), key=lambda x: int(x) if x.isdigit() else x)
    if not case_names:
        raise ValueError(
            f"No `{split_name}` cases found for system={normalized_system}, fault_category={fault_category}"
        )
    return case_names


def resolve_paths_from_config(config: Dict[str, Any]) -> Dict[str, Path]:
    model_conf = config.get("model", {}) or {}
    diag_conf = config.get("diagnosis", {}) or {}

    model_name = str(model_conf.get("model", "")).strip()
    fault_category = str(diag_conf.get("fault_category", "")).strip()
    normalized_system = normalize_system_name(diag_conf.get("system", ""))
    dataset_root = Path(str(diag_conf.get("dataset_root", "") or "")).expanduser()
    save_root = Path(str(diag_conf.get("save_root", "") or "")).expanduser()

    if not model_name:
        raise ValueError("Missing `model.model` in config")
    if not fault_category:
        raise ValueError("Missing `diagnosis.fault_category` in config")
    if not str(dataset_root):
        raise ValueError("Missing `diagnosis.dataset_root` in config")
    if not str(save_root):
        raise ValueError("Missing `diagnosis.save_root` in config")

    label_root = dataset_root / "process-label" / normalized_system / fault_category
    agent_root = save_root / normalized_system / model_name / fault_category
    out_root = agent_root.parent
    return {
        "label_root": label_root,
        "agent_root": agent_root,
        "summary_out": out_root / f"evaluation_v2_{fault_category}_summary.json",
        "detail_out": out_root / f"evaluation_v2_{fault_category}_details.json",
    }


def load_ground_truth(label_root: Path, case_name: str) -> Dict[str, Any]:
    label_path = label_root / case_name / "milestone.json"
    if not label_path.exists():
        raise FileNotFoundError(f"Missing process label: {label_path}")
    label = read_json(label_path)
    result = label.get("result", {})
    if not isinstance(result, dict):
        raise ValueError(f"Invalid result field in {label_path}")
    return result


def _remove_getalerts_credit(data: Dict[str, Any]) -> None:
    """Disable GetAlerts-only process credit for gated performance cases."""

    for milestone in data.get("milestones", []) or []:
        milestone["admissible_tool_uses"] = [
            tool_use
            for tool_use in milestone.get("admissible_tool_uses", []) or []
            if tool_use.get("tool_name") != "GetAlerts"
        ]

        retained_groups = []
        for group in milestone.get("admissible_evidence_groups", []) or []:
            tool_uses = group.get("tool_uses", []) or []
            if any(tool_use.get("tool_name") == "GetAlerts" for tool_use in tool_uses):
                continue
            retained_groups.append(group)
        milestone["admissible_evidence_groups"] = retained_groups


def load_process_annotation(
    label_root: Path, case_name: str, *, disable_getalerts_credit: bool = False
) -> CaseAnnotation:
    label_path = label_root / case_name / "milestone.json"
    data = read_json(label_path)
    if disable_getalerts_credit:
        _remove_getalerts_credit(data)
    for milestone in data.get("milestones", []) or []:
        milestone.setdefault("description", "")
        milestone.setdefault("role", "")
    return CaseAnnotation.from_dict(data)


def iter_tool_steps(case_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        step
        for step in case_data.get("steps", []) or []
        if step.get("action_type") == "tool" and step.get("action_name")
    ]


def invalid_tool_actions(case_data: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
    invalid = []
    for step in case_data.get("steps", []) or []:
        action_type = step.get("action_type")
        if action_type == "invalid":
            reason = "invalid_model_output"
        elif action_type != "tool":
            continue
        elif step.get("error"):
            reason = "tool_error"
        elif not step.get("action_name"):
            reason = "missing_action_name"
        elif not isinstance(step.get("action_input"), dict):
            reason = "invalid_action_input"
        else:
            reason = ""
        if reason:
            invalid.append(
                {
                    "step_id": step.get("step_id"),
                    "action_name": step.get("action_name"),
                    "action_input": step.get("action_input"),
                    "reason": reason,
                    "error": step.get("error"),
                }
            )
    return len(invalid), invalid


def final_answer_step_present(case_data: Dict[str, Any]) -> bool:
    if case_data.get("final_answer"):
        return True
    return any(step.get("final_answer") for step in case_data.get("steps", []) or [])


def agent_trajectory(case_data: Dict[str, Any]) -> List[TrajectoryStep]:
    trajectory: List[TrajectoryStep] = []
    for step in iter_tool_steps(case_data):
        arguments = step.get("action_input")
        if not isinstance(arguments, dict):
            arguments = {}
        trajectory.append(
            TrajectoryStep(
                tool_call=ToolCall(
                    tool_name=str(step.get("action_name", "")),
                    arguments=arguments,
                    raw="",
                ),
                observation=step.get("observation", ""),
            )
        )
    return trajectory


def tool_signature(step: Dict[str, Any]) -> str:
    arguments = step.get("action_input")
    if not isinstance(arguments, dict):
        arguments = {}
    return f"{step.get('action_name', '')}:{json.dumps(arguments, sort_keys=True, ensure_ascii=False)}"


def redundant_action_rate(tool_steps: List[Dict[str, Any]]) -> float:
    total = len(tool_steps)
    if total == 0:
        return 0.0
    counts: Dict[str, int] = {}
    for step in tool_steps:
        sig = tool_signature(step)
        counts[sig] = counts.get(sig, 0) + 1
    redundant = sum(count - 1 for count in counts.values())
    return redundant / total


def process_scores(
    label_root: Path,
    case_name: str,
    case_data: Dict[str, Any],
    *,
    disable_getalerts_credit: bool = False,
) -> Dict[str, float]:
    annotation = load_process_annotation(
        label_root,
        case_name,
        disable_getalerts_credit=disable_getalerts_credit,
    )
    result = evaluate_trajectory(annotation, agent_trajectory(case_data))
    return {
        "MC": result.milestone_coverage,
        "EOC": result.evidence_order_coverage,
        "ECR": 1.0 if result.process_complete else 0.0,
        "EE": result.evidence_efficiency,
    }


def prediction_scores(predictions: List[Dict[str, Any]], gt: Dict[str, Any]) -> Dict[str, float]:
    gt_component = normalize_text(gt.get("fault_object"))
    gt_root_cause = normalize_text(gt.get("root_cause"))

    ca_at_1 = 0.0
    fa_at_1 = 0.0
    jra_at_1 = 0.0

    for idx, pred in enumerate(predictions[:1]):
        component_ok = normalize_text(pred.get("fault_object")) == gt_component
        fault_type_ok = normalize_text(pred.get("root_cause")) == gt_root_cause
        joint_ok = component_ok and fault_type_ok
        if idx == 0:
            ca_at_1 = float(component_ok)
            fa_at_1 = float(fault_type_ok)
            jra_at_1 = float(joint_ok)

    return {
        "CA": ca_at_1,
        "FA": fa_at_1,
        "JRA": jra_at_1,
    }


def evaluate_case(case_name: str, label_root: Path, agent_root: Path) -> Dict[str, Any]:
    label_path = label_root / case_name / "milestone.json"
    agent_path = agent_root / case_name / f"{case_name}.json"
    detail: Dict[str, Any] = {
        "case_name": case_name,
        "label_path": str(label_path),
        "agent_path": str(agent_path),
        "agent_case_exists": agent_path.exists(),
    }

    if not label_path.exists():
        detail["error"] = "missing_process_label"
        detail["metrics"] = {
            **prediction_scores([], {}),
            "MC": 0.0,
            "EOC": 0.0,
            "ECR": 0.0,
            "EE": 0.0,
            "steps": 0.0,
            "RAR": 0.0,
            "invalid_actions": 0.0,
        }
        return detail
    if not agent_path.exists():
        detail["ground_truth"] = load_ground_truth(label_root, case_name)
        detail["error"] = "missing_agent_case_json"
        detail["metrics"] = {
            **prediction_scores([], detail["ground_truth"]),
            "MC": 0.0,
            "EOC": 0.0,
            "ECR": 0.0,
            "EE": 0.0,
            "steps": 0.0,
            "RAR": 0.0,
            "invalid_actions": 0.0,
        }
        return detail

    gt = load_ground_truth(label_root, case_name)
    case_data = read_agent_case_for_evaluation(agent_path)
    parsed_final_answer, final_answer_source = extract_final_answer_payload(case_data)
    predictions = parsed_final_answer.get("top_3_predictions", []) if parsed_final_answer else []
    tool_steps = iter_tool_steps(case_data)
    tool_call_count = len(tool_steps)
    final_answer_count = 1 if final_answer_step_present(case_data) else 0
    invalid_count, invalid_details = invalid_tool_actions(case_data)
    prediction_metrics = prediction_scores(predictions, gt)
    disable_getalerts_credit = label_root.name == "performance" and prediction_metrics["CA"] < 1.0
    metrics = {
        **prediction_metrics,
        **process_scores(
            label_root,
            case_name,
            case_data,
            disable_getalerts_credit=disable_getalerts_credit,
        ),
        "steps": float(tool_call_count + final_answer_count),
        "RAR": redundant_action_rate(tool_steps),
        "invalid_actions": float(invalid_count),
    }

    detail.update(
        {
            "ground_truth": gt,
            "final_answer_source": final_answer_source,
            "top_3_predictions": predictions,
            "tool_call_count": tool_call_count,
            "final_answer_step_count": final_answer_count,
            "invalid_action_details": invalid_details,
            "metrics": metrics,
        }
    )
    if not parsed_final_answer:
        detail["error"] = "unparsed_final_answer"
    return detail


def summarize(details: List[Dict[str, Any]], paths: Dict[str, Path], config: Dict[str, Any]) -> Dict[str, Any]:
    metric_names = ["CA", "FA", "JRA", "MC", "EOC", "ECR", "EE", "steps", "RAR", "invalid_actions"]
    total_cases = sum(1 for path in paths["label_root"].iterdir() if path.is_dir())
    selected_cases = len(details)
    run_details = [detail for detail in details if detail.get("agent_case_exists")]
    run_cases = len(run_details)
    sums = {name: 0.0 for name in metric_names}
    errors: Dict[str, int] = {}
    by_root: Dict[str, Dict[str, Any]] = {}

    for detail in details:
        if detail.get("error"):
            errors[detail["error"]] = errors.get(detail["error"], 0) + 1

    for detail in run_details:
        for name in metric_names:
            sums[name] += float(detail.get("metrics", {}).get(name, 0.0))

        root = str((detail.get("ground_truth") or {}).get("root_cause", "unknown"))
        bucket = by_root.setdefault(root, {"n": 0, **{name: 0.0 for name in metric_names}})
        bucket["n"] += 1
        for name in metric_names:
            bucket[name] += float(detail.get("metrics", {}).get(name, 0.0))

    by_root_summary = {}
    for root, bucket in sorted(by_root.items()):
        n = bucket["n"]
        by_root_summary[root] = {
            "n": n,
            **{name: round(bucket[name] / n, 4) if n else 0.0 for name in metric_names},
        }

    return {
        "config": {
            "config_path": str(CONFIG_PATH),
            "system": config.get("diagnosis", {}).get("system"),
            "fault_category": config.get("diagnosis", {}).get("fault_category"),
            "case_split": config.get("diagnosis", {}).get("case_split", ""),
            "case_split_file": config.get("diagnosis", {}).get("case_split_file", ""),
            "label_root": str(paths["label_root"]),
            "agent_root": str(paths["agent_root"]),
        },
        "counts": {
            "total_cases": total_cases,
            "selected_cases": selected_cases,
            "run_cases": run_cases,
            "missing_run_cases": selected_cases - run_cases,
            "invalid_action_total": int(sums["invalid_actions"]),
            **errors,
        },
        "metrics": {name: round(sums[name] / run_cases, 4) if run_cases else 0.0 for name in metric_names},
        "by_root_cause": by_root_summary,
    }


def print_summary(summary: Dict[str, Any]) -> None:
    print("Outcome Evaluation v2")
    print("=" * 80)
    for key, value in summary["config"].items():
        print(f"{key}: {value}")
    print("-" * 80)
    for key, value in summary["counts"].items():
        print(f"{key}: {value}")
    print("-" * 80)
    for key, value in summary["metrics"].items():
        display_name = METRIC_DISPLAY_NAMES.get(key)
        label = f"{key} ({display_name})" if display_name else key
        print(f"{label}: {value}")


def main() -> None:
    config = load_eval_config()
    diag_conf = config.get("diagnosis", {}) or {}
    paths = resolve_paths_from_config(config)
    label_root = paths["label_root"]
    agent_root = paths["agent_root"]

    if not label_root.exists():
        raise FileNotFoundError(f"Process-label root not found: {label_root}")
    if not agent_root.exists():
        raise FileNotFoundError(f"Agent result root not found: {agent_root}")

    normalized_system = normalize_system_name(diag_conf.get("system", ""))
    fault_category = str(diag_conf.get("fault_category", "")).strip()
    case_name = str(diag_conf.get("case_name", "") or "").strip()
    if case_name:
        case_names = [case_name]
    else:
        split_case_names = resolve_case_names_from_split(diag_conf, normalized_system, fault_category)
        if split_case_names is not None:
            case_names = split_case_names
        else:
            case_names = sorted((p.name for p in label_root.iterdir() if p.is_dir()), key=lambda x: int(x) if x.isdigit() else x)

    details = [evaluate_case(case, label_root, agent_root) for case in case_names]
    summary = summarize(details, paths, config)
    paths["summary_out"].write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["detail_out"].write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary(summary)
    print("-" * 80)
    print(f"Summary JSON: {paths['summary_out']}")
    print(f"Detail JSON: {paths['detail_out']}")


if __name__ == "__main__":
    main()
