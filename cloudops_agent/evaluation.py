#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "model_configs.yaml"


TOOL_KEY_PARAMS = {
    "GetResources": ["resource_type"],
    "DescribeResource": ["resource_type", "name"],
    "CheckNodeServiceStatus": ["node_name", "service_name"],
    "GetClusterConfiguration": [],
    "GetAlerts": [],
    "GetErrorLogs": ["service_name"],
    "GetRecentLogs": ["service_name"],
    "GetServiceDependencies": ["service_name"],
    "GetAppYAML": ["app_name"],
    "CheckServiceConnectivity": ["service_name", "port"],
}

TOOL_REQUIRED_PARAMS = {
    "GetResources": ["resource_type"],
    "DescribeResource": ["resource_type", "name"],
    "CheckNodeServiceStatus": ["node_name", "service_name"],
    "GetClusterConfiguration": [],
    "GetAlerts": [],
    "GetErrorLogs": ["service_name"],
    "GetRecentLogs": ["service_name"],
    "GetServiceDependencies": ["service_name"],
    "GetAppYAML": ["app_name"],
    "CheckServiceConnectivity": ["service_name", "port"],
}

RESOURCE_ALIASES_DB = {
    "pod": "pods", "pods": "pods", "po": "pods",
    "service": "services", "services": "services", "svc": "services",
    "deployment": "deployments", "deployments": "deployments", "deploy": "deployments",
    "statefulset": "statefulsets", "statefulsets": "statefulsets", "sts": "statefulsets",
    "daemonset": "daemonsets", "daemonsets": "daemonsets", "ds": "daemonsets",
    "configmap": "configmaps", "configmaps": "configmaps", "cm": "configmaps",
    "secret": "secrets", "secrets": "secrets",
    "persistentvolumeclaim": "persistentvolumeclaims", "persistentvolumeclaims": "persistentvolumeclaims", "pvc": "persistentvolumeclaims",
    "replicaset": "replicasets", "replicasets": "replicasets", "rs": "replicasets",
    "ingress": "ingresses", "ingresses": "ingresses", "ing": "ingresses",
    "networkpolicy": "networkpolicies", "networkpolicies": "networkpolicies", "netpol": "networkpolicies",
    "serviceaccount": "serviceaccounts", "serviceaccounts": "serviceaccounts", "sa": "serviceaccounts",
    "job": "jobs", "jobs": "jobs",
    "endpoint": "endpoints", "endpoints": "endpoints", "ep": "endpoints",
    "persistentvolume": "persistentvolumes", "persistentvolumes": "persistentvolumes", "pv": "persistentvolumes",
    "namespace": "namespaces", "namespaces": "namespaces", "ns": "namespaces",
    "node": "nodes", "nodes": "nodes", "no": "nodes",
    "storageclass": "storageclasses", "storageclasses": "storageclasses", "sc": "storageclasses",
    "event": "events", "events": "events",
    "resourcequota": "resourcequota", "resourcequotas": "resourcequota",
}


def normalize_system_name(system: str) -> str:
    system_key = str(system or "").strip().lower()
    if system_key in {"trainticket", "train-ticket"}:
        return "trainticket"
    if system_key == "boutique":
        return "boutique"
    raise ValueError(f"Unsupported system: {system}")


def load_eval_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")

    if yaml is not None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        config = load_simple_yaml_config(CONFIG_PATH)

    if not isinstance(config, dict):
        raise ValueError("Invalid config format: expected top-level mapping")
    return config


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


def resolve_paths_from_config(config: Dict[str, Any]) -> Dict[str, Path]:
    model_conf = config.get("model", {})
    diag_conf = config.get("diagnosis", {})

    model_name = str(model_conf.get("model", "")).strip()
    prompt_strategy = str(diag_conf.get("prompt_strategy", "")).strip()
    fault_category = str(diag_conf.get("fault_category", "")).strip()
    normalized_system = normalize_system_name(diag_conf.get("system", ""))

    if not model_name:
        raise ValueError("Missing `model.model` in config")
    if not prompt_strategy:
        raise ValueError("Missing `diagnosis.prompt_strategy` in config")
    if not fault_category:
        raise ValueError("Missing `diagnosis.fault_category` in config")

    dataset_root = Path(diag_conf.get("dataset_root", "")).expanduser()
    save_root = Path(diag_conf.get("save_root", "")).expanduser()
    if not str(dataset_root):
        raise ValueError("Missing `diagnosis.dataset_root` in config")
    if not str(save_root):
        raise ValueError("Missing `diagnosis.save_root` in config")

    gt_root = dataset_root / "benchmark" / normalized_system / fault_category
    agent_root = save_root / normalized_system / f"{model_name}_{prompt_strategy}" / fault_category
    summary_out = agent_root.parent / f"evaluation_{fault_category}_summary.json"
    detail_out = agent_root.parent / f"evaluation_{fault_category}_details.json"

    return {
        "gt_root": gt_root,
        "agent_root": agent_root,
        "summary_out": summary_out,
        "detail_out": detail_out,
    }


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_resource_type(value: Any) -> str:
    text = normalize_text(value)
    return RESOURCE_ALIASES_DB.get(text, text)


def strip_pod_suffix(name: Any) -> str:
    if not isinstance(name, str):
        return str(name)
    patterns = [
        r"^([a-z0-9-]+)-[a-f0-9]{8,10}-[a-z0-9]{4,6}$",
        r"^([a-z0-9-]+)-[a-z0-9]{5}$",
    ]
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            return match.group(1)
    return name


def parse_json_maybe(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    block_patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
    ]
    for pattern in block_patterns:
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
    for step in reversed(case_data.get("steps", [])):
        if step.get("final_answer"):
            candidates.append((f"step_{step.get('step_id', 'unknown')}_final_answer", step.get("final_answer")))
        if step.get("raw_model_output"):
            candidates.append((f"step_{step.get('step_id', 'unknown')}_raw_model_output", step.get("raw_model_output")))

    for source, candidate in candidates:
        parsed = parse_json_maybe(candidate)
        if parsed and isinstance(parsed.get("top_3_predictions"), list):
            return parsed, source
    return None, "unparsed"


def compare_prediction(pred: Dict[str, Any], gt: Dict[str, Any]) -> Tuple[bool, bool]:
    gt_tax = normalize_text(gt.get("fault_taxonomy"))
    gt_obj = normalize_text(gt.get("fault_object"))
    gt_root = normalize_text(gt.get("root_cause"))
    pr_tax = normalize_text(pred.get("fault_taxonomy"))
    pr_obj = normalize_text(pred.get("fault_object"))
    pr_root = normalize_text(pred.get("root_cause"))
    full_match = pr_tax == gt_tax and pr_obj == gt_obj and pr_root == gt_root
    partial_match = pr_obj == gt_obj and pr_root == gt_root
    return full_match, partial_match


def score_predictions(predictions: List[Dict[str, Any]], gt: Dict[str, Any]) -> Dict[str, float]:
    a1 = 0.0
    a3 = 0.0
    partial_a1 = 0.0
    partial_a3 = 0.0
    for idx, pred in enumerate(predictions[:3]):
        full_match, partial_match = compare_prediction(pred, gt)
        if full_match:
            if idx == 0:
                a1 = 1.0
            a3 = 1.0
        if partial_match:
            if idx == 0:
                partial_a1 = 1.0
            partial_a3 = 1.0
    return {
        "a1": a1,
        "a3": a3,
        "partial_a1": partial_a1,
        "partial_a3": partial_a3,
    }


def normalize_value_for_param(tool_name: str, param: str, value: Any) -> str:
    if param == "resource_type":
        return normalize_resource_type(value)
    if param == "name" and normalize_resource_type(value if tool_name == "GetResources" else "") == "pods":
        return strip_pod_suffix(value)
    if tool_name == "DescribeResource" and param == "name":
        return str(value).strip()
    return str(value).strip()


def standardize_tool_step(step: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    action_name = step.get("action_name")
    action_input = step.get("action_input")
    if not action_name or not isinstance(action_name, str):
        return None, "missing_action_name"
    if not isinstance(action_input, dict):
        return None, "invalid_action_input"

    required = TOOL_REQUIRED_PARAMS.get(action_name, [])
    for key in required:
        val = action_input.get(key)
        if val is None or str(val).strip() == "":
            return None, f"missing_required_param:{key}"

    if action_name == "GetResources":
        resource_type = normalize_resource_type(action_input.get("resource_type"))
        if not resource_type:
            return None, "missing_required_param:resource_type"
        return f"{action_name}::{resource_type}", None

    if action_name == "DescribeResource":
        resource_type = normalize_resource_type(action_input.get("resource_type"))
        name = action_input.get("name")
        if resource_type == "pods":
            name = strip_pod_suffix(name)
        elif name is not None:
            name = str(name).strip()
        if not resource_type or not name:
            return None, "missing_describe_resource_fields"
        return f"{action_name}::{resource_type}::{name}", None

    params = TOOL_KEY_PARAMS.get(action_name)
    if params is None:
        params = sorted(k for k in action_input.keys() if k != "namespace")

    parts = [action_name]
    for key in params:
        if key == "namespace":
            continue
        value = action_input.get(key)
        if value is None or str(value).strip() == "":
            continue
        parts.append(str(value).strip())
    if len(parts) == 1:
        parts.append("")
    return "::".join(parts), None


def standardize_agent_steps(case_data: Dict[str, Any]) -> Tuple[List[str], int, List[str]]:
    standardized: List[str] = []
    invalid_reasons: List[str] = []
    invalid_count = 0
    for step in case_data.get("steps", []):
        if step.get("action_type") != "tool":
            continue
        if step.get("error"):
            invalid_count += 1
            invalid_reasons.append(f"step_{step.get('step_id', 'unknown')}:error")
            continue
        standardized_step, reason = standardize_tool_step(step)
        if reason:
            invalid_count += 1
            invalid_reasons.append(f"step_{step.get('step_id', 'unknown')}:{reason}")
            continue
        standardized.append(standardized_step)
    return standardized, invalid_count, invalid_reasons


def precision_recall_f1(agent_steps: List[str], expert_steps: List[str]) -> Tuple[float, float, float]:
    if not agent_steps and not expert_steps:
        return 1.0, 1.0, 1.0
    if not agent_steps:
        return 0.0, 0.0, 0.0
    agent_set = set(agent_steps)
    expert_set = set(expert_steps)
    intersection = len(agent_set & expert_set)
    precision = intersection / len(agent_set) if agent_set else 0.0
    recall = intersection / len(expert_set) if expert_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return precision, recall, f1


def in_order_match(expert_steps: List[str], agent_steps: List[str]) -> float:
    if not expert_steps:
        return 1.0
    idx = 0
    for step in agent_steps:
        if step == expert_steps[idx]:
            idx += 1
            if idx == len(expert_steps):
                return 1.0
    return 0.0


def any_order_match(expert_steps: List[str], agent_steps: List[str]) -> float:
    if not expert_steps:
        return 1.0
    return 1.0 if set(expert_steps).issubset(set(agent_steps)) else 0.0


def exact_match(expert_steps: List[str], agent_steps: List[str]) -> float:
    return 1.0 if expert_steps == agent_steps else 0.0


def choose_best_path(agent_steps: List[str], process: Dict[str, List[str]]) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    for path_name in ("path1", "path2"):
        expert_steps = process.get(path_name, [])
        precision, recall, f1 = precision_recall_f1(agent_steps, expert_steps)
        current = {
            "matched_path": path_name,
            "expert_steps": expert_steps,
            "rel": precision,
            "cov": recall,
            "f1": f1,
            "in_order": in_order_match(expert_steps, agent_steps),
            "exact": exact_match(expert_steps, agent_steps),
            "any_order": any_order_match(expert_steps, agent_steps),
        }
        if best is None:
            best = current
            continue
        if current["f1"] > best["f1"]:
            best = current
            continue
        if current["f1"] == best["f1"] and current["in_order"] > best["in_order"]:
            best = current
    return best or {
        "matched_path": "path1",
        "expert_steps": [],
        "rel": 0.0,
        "cov": 0.0,
        "f1": 0.0,
        "in_order": 0.0,
        "exact": 0.0,
        "any_order": 0.0,
    }


def calculate_rar(agent_steps: List[str]) -> float:
    total = len(agent_steps)
    if total == 0:
        return 0.0
    counts: Dict[str, int] = {}
    for step in agent_steps:
        counts[step] = counts.get(step, 0) + 1
    redundant = sum(count - 1 for count in counts.values())
    return redundant / total


def calculate_total_latency(case_data: Dict[str, Any]) -> float:
    total = 0.0
    for step in case_data.get("steps", []):
        model_latency = step.get("model_latency")
        tool_latency = step.get("tool_latency")
        if isinstance(model_latency, (int, float)):
            total += float(model_latency)
        if isinstance(tool_latency, (int, float)):
            total += float(tool_latency)
    return total


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(case_name: str, gt_root: Path, agent_root: Path) -> Dict[str, Any]:
    gt_path = gt_root / case_name / "metadata.json"
    agent_path = agent_root / case_name / f"{case_name}.json"

    detail: Dict[str, Any] = {
        "case_name": case_name,
        "gt_path": str(gt_path),
        "agent_path": str(agent_path),
    }

    if not gt_path.exists():
        detail["error"] = "missing_gt_metadata"
        return detail
    if not agent_path.exists():
        detail["error"] = "missing_agent_case_json"
        return detail

    gt = read_json(gt_path)
    case_data = read_json(agent_path)
    detail["ground_truth"] = gt.get("result", {})

    parsed_final_answer, final_answer_source = extract_final_answer_payload(case_data)
    detail["final_answer_source"] = final_answer_source
    detail["parsed_final_answer"] = parsed_final_answer

    predictions = parsed_final_answer.get("top_3_predictions", []) if parsed_final_answer else []
    detail["top_3_predictions"] = predictions
    tcr = 1.0 if predictions else 0.0
    outcome_scores = score_predictions(predictions, gt.get("result", {})) if predictions else {
        "a1": 0.0,
        "a3": 0.0,
        "partial_a1": 0.0,
        "partial_a3": 0.0,
    }

    agent_steps, invalid_count, invalid_reasons = standardize_agent_steps(case_data)
    best_path = choose_best_path(agent_steps, gt.get("process", {}))
    steps = len(agent_steps)
    total_latency = calculate_total_latency(case_data)
    ztdr = 1.0 if steps == 0 and predictions else 0.0
    rar = calculate_rar(agent_steps)

    detail["standardized_agent_steps"] = agent_steps
    detail["matched_path"] = best_path["matched_path"]
    detail["expert_steps"] = best_path["expert_steps"]
    detail["invalid_reasons"] = invalid_reasons
    detail["metrics"] = {
        **outcome_scores,
        "tcr": tcr,
        "exact": best_path["exact"],
        "in_order": best_path["in_order"],
        "any_order": best_path["any_order"],
        "rel": best_path["rel"],
        "cov": best_path["cov"],
        "steps": float(steps),
        "mtti": total_latency,
        "iac": float(invalid_count),
        "rar": rar,
        "ztdr": ztdr,
    }
    if not parsed_final_answer:
        detail["error"] = "unparsed_final_answer"
    return detail


def summarize(details: List[Dict[str, Any]], gt_root: Path, agent_root: Path, config_path: Path) -> Dict[str, Any]:
    total_cases = len(details)
    metric_names = [
        "a1",
        "a3",
        "partial_a1",
        "partial_a3",
        "tcr",
        "exact",
        "in_order",
        "any_order",
        "rel",
        "cov",
        "steps",
        "mtti",
        "iac",
        "rar",
        "ztdr",
    ]
    sums = {name: 0.0 for name in metric_names}
    missing_gt = 0
    missing_agent = 0
    parse_failures = 0

    for detail in details:
        error = detail.get("error")
        if error == "missing_gt_metadata":
            missing_gt += 1
        if error == "missing_agent_case_json":
            missing_agent += 1
        if error == "unparsed_final_answer":
            parse_failures += 1
        metrics = detail.get("metrics", {})
        for name in metric_names:
            sums[name] += float(metrics.get(name, 0.0))

    averages = {name: round(sums[name] / total_cases, 4) if total_cases else 0.0 for name in metric_names}
    return {
        "config": {
            "config_path": str(config_path),
            "gt_root": str(gt_root),
            "agent_root": str(agent_root),
            "resource_alias_source": "inlined in evaluation.py",
        },
        "counts": {
            "total_cases": total_cases,
            "missing_gt_metadata": missing_gt,
            "missing_agent_case_json": missing_agent,
            "final_answer_parse_failures": parse_failures,
        },
        "metrics": {
            "Accuracy @1": averages["a1"],
            "Accuracy @3": averages["a3"],
            "Partial Accuracy @1": averages["partial_a1"],
            "Partial Accuracy @3": averages["partial_a3"],
            "Task Completion Rate": averages["tcr"],
            "ExactMatch": averages["exact"],
            "InOrder": averages["in_order"],
            "AnyOrder": averages["any_order"],
            "Relevant": averages["rel"],
            "Coverage": averages["cov"],
            "Steps": round(averages["steps"], 2),
            "Mean Time to Identify": round(averages["mtti"], 4),
            "Invalid Action Count": round(averages["iac"], 2),
            "Redundant Action Rate": averages["rar"],
            # "ZTDR": averages["ztdr"],
        },
    }


def print_summary(summary: Dict[str, Any]) -> None:
    print("Evaluation Summary")
    print("=" * 80)
    for key, value in summary["config"].items():
        print(f"{key}: {value}")
    print("-" * 80)
    for key, value in summary["counts"].items():
        print(f"{key}: {value}")
    print("-" * 80)
    for key, value in summary["metrics"].items():
        print(f"{key}: {value}")


def main() -> None:
    config = load_eval_config()
    resolved_paths = resolve_paths_from_config(config)
    gt_root = resolved_paths["gt_root"]
    agent_root = resolved_paths["agent_root"]
    summary_out = resolved_paths["summary_out"]
    detail_out = resolved_paths["detail_out"]
    case_name = config.get("diagnosis", {}).get("case_name")

    if not gt_root.exists():
        raise FileNotFoundError(f"Ground-truth root not found: {gt_root}")
    if not agent_root.exists():
        raise FileNotFoundError(f"Agent result root not found: {agent_root}")

    if case_name is not None and str(case_name).strip():
        case_names = [str(case_name).strip()]
    else:
        case_names = sorted(p.name for p in gt_root.iterdir() if p.is_dir())

    details = [evaluate_case(case_name, gt_root, agent_root) for case_name in case_names]
    summary = summarize(details, gt_root, agent_root, CONFIG_PATH)
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detail_out.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary(summary)
    print("-" * 80)
    print(f"Summary JSON: {summary_out}")
    print(f"Detail JSON: {detail_out}")


if __name__ == "__main__":
    main()
