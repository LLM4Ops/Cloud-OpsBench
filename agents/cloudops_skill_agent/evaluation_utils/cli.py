from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict

from .enumerator import enumerate_q_candidates
from .evaluator import evaluate_trajectory
from .io import build_tool_cache_index, load_annotations, load_golden_trajectory, load_tool_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate diagnostic evidence graph annotations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate a trajectory.")
    evaluate_parser.add_argument("--annotations", required=True, help="Annotation JSON file.")
    evaluate_parser.add_argument("--case-id", required=True, help="Case id, e.g. boutique/service/1.")
    evaluate_parser.add_argument("--trajectory", required=True, help="Golden trajectory JSON or tool_cache.json.")
    evaluate_parser.add_argument(
        "--trajectory-kind",
        choices=("golden", "tool-cache"),
        default="golden",
        help="Input trajectory format.",
    )

    metrics_parser = subparsers.add_parser(
        "process-metrics",
        help="Compute MC, EOC, and Evidence Efficiency for one or more trajectories.",
    )
    metrics_parser.add_argument(
        "trajectory",
        nargs="?",
        help="Path to one golden trajectory JSON. If omitted with --all, scan a tree.",
    )
    metrics_parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all path*.json trajectories under --trajectory-root.",
    )
    metrics_parser.add_argument(
        "--trajectory-root",
        default="golden-trajectory",
        help="Root used by --all.",
    )
    metrics_parser.add_argument(
        "--annotation-root",
        default="annotations",
        help="Annotation root used to infer matching annotation_v2.json files.",
    )
    metrics_parser.add_argument("--app", choices=("boutique", "trainticket"))
    metrics_parser.add_argument("--category", help="Optional fault category filter.")
    metrics_parser.add_argument("--root-cause", help="Optional root-cause filter.")
    metrics_parser.add_argument(
        "--no-details",
        action="store_true",
        help="Only print aggregate rows.",
    )

    index_parser = subparsers.add_parser("index-tool-cache", help="Build a compact tool cache index.")
    index_parser.add_argument("tool_cache", help="Path to tool_cache.json.")

    enumerate_parser = subparsers.add_parser(
        "enumerate-q",
        help="Enumerate milestone candidate tool uses from a tool_cache.json.",
    )
    enumerate_parser.add_argument("--annotations", required=True, help="Annotation JSON file.")
    enumerate_parser.add_argument(
        "--case-id",
        help="Case id when the annotation file contains multiple cases.",
    )
    enumerate_parser.add_argument("--tool-cache", required=True, help="Path to tool_cache.json.")
    enumerate_parser.add_argument(
        "--mode",
        choices=("evidence-only", "strict"),
        default="evidence-only",
        help="Use evidence-only discovery or require current annotated tool/args.",
    )
    enumerate_parser.add_argument(
        "--preview-chars",
        type=int,
        default=240,
        help="Observation preview length for each candidate.",
    )

    args = parser.parse_args()
    if args.command == "evaluate":
        return _evaluate(args)
    if args.command == "process-metrics":
        return _process_metrics(args)
    if args.command == "index-tool-cache":
        print(json.dumps(build_tool_cache_index(args.tool_cache), ensure_ascii=False, indent=2))
        return 0
    if args.command == "enumerate-q":
        return _enumerate_q(args)
    return 2


def _evaluate(args: argparse.Namespace) -> int:
    annotations = {item.case_id: item for item in load_annotations(args.annotations)}
    if args.case_id not in annotations:
        raise SystemExit(f"case id not found in annotations: {args.case_id}")

    if args.trajectory_kind == "golden":
        steps = load_golden_trajectory(args.trajectory)
    else:
        steps = load_tool_cache(args.trajectory)

    result = evaluate_trajectory(annotations[args.case_id], steps)
    print(json.dumps(_result_to_dict(result), ensure_ascii=False, indent=2))
    return 0 if result.process_complete else 1


def _process_metrics(args: argparse.Namespace) -> int:
    trajectory_paths = _collect_trajectory_paths(args)
    rows = []
    for trajectory_path in trajectory_paths:
        annotation_path = _find_annotation_for_trajectory(
            trajectory_path, Path(args.annotation_root)
        )
        annotation = load_annotations(annotation_path)[0]
        root_cause = str(annotation.result.get("root_cause", ""))
        app, category, case_number, path_name = _trajectory_parts(trajectory_path)
        if args.app and app != args.app:
            continue
        if args.category and category != args.category:
            continue
        if args.root_cause and root_cause != args.root_cause:
            continue

        result = evaluate_trajectory(annotation, load_golden_trajectory(trajectory_path))
        rows.append(
            {
                "app": app,
                "category": category,
                "root_cause": root_cause,
                "case": case_number,
                "path": path_name,
                "mc": result.milestone_coverage,
                "eoc": result.evidence_order_coverage,
                "ee": result.evidence_efficiency,
                "established": len(result.established),
                "ordered": len(result.ordered),
                "milestones": result.milestone_count,
                "evidence_tools": result.evidence_tool_count,
                "total_tools": result.total_tool_calls,
                "process_complete": result.process_complete,
                "missing": list(result.missing),
            }
        )

    if not rows:
        print("No trajectories matched.")
        return 1

    if not args.no_details:
        print("Per-trajectory metrics")
        print(
            "app\tcategory\troot_cause\tcase\tpath\tMC\tEOC\tEE\t"
            "est/total\tord/total\tevidence_tools/total_tools\tmissing"
        )
        for row in rows:
            print(
                "\t".join(
                    [
                        row["app"],
                        row["category"],
                        row["root_cause"],
                        row["case"],
                        row["path"],
                        _fmt(row["mc"]),
                        _fmt(row["eoc"]),
                        _fmt(row["ee"]),
                        f"{row['established']}/{row['milestones']}",
                        f"{row['ordered']}/{row['milestones']}",
                        f"{row['evidence_tools']}/{row['total_tools']}",
                        ",".join(row["missing"]),
                    ]
                )
            )
        print()

    _print_aggregate("Overall", rows, lambda row: ("overall",))
    _print_aggregate("By app", rows, lambda row: (row["app"],))
    _print_aggregate("By category", rows, lambda row: (row["app"], row["category"]))
    _print_aggregate(
        "By root cause",
        rows,
        lambda row: (row["app"], row["category"], row["root_cause"]),
    )
    return 0


def _enumerate_q(args: argparse.Namespace) -> int:
    annotations = load_annotations(args.annotations)
    if args.case_id:
        annotation_by_case = {item.case_id: item for item in annotations}
        if args.case_id not in annotation_by_case:
            raise SystemExit(f"case id not found in annotations: {args.case_id}")
        annotation = annotation_by_case[args.case_id]
    elif len(annotations) == 1:
        annotation = annotations[0]
    else:
        raise SystemExit("--case-id is required when annotation file contains multiple cases")

    result = enumerate_q_candidates(
        annotation,
        load_tool_cache(args.tool_cache),
        strict=args.mode == "strict",
        preview_chars=args.preview_chars,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _collect_trajectory_paths(args: argparse.Namespace) -> list[Path]:
    if args.all:
        root = Path(args.trajectory_root)
        return sorted(root.glob("*/*/*/path*.json"))
    if not args.trajectory:
        raise SystemExit("provide a trajectory path or use --all")
    return [Path(args.trajectory)]


def _find_annotation_for_trajectory(
    trajectory_path: Path, annotation_root: Path
) -> Path:
    app, category, case_number, _ = _trajectory_parts(trajectory_path)
    candidates = sorted(
        annotation_root.glob(f"{app}/{category}/*/{case_number}/annotation_v2.json")
    )
    if not candidates:
        candidates = sorted(
            annotation_root.glob(f"{app}/{category}/*/{case_number}/annotation.json")
        )
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one annotation for {trajectory_path}, found {len(candidates)}"
        )
    return candidates[0]


def _trajectory_parts(trajectory_path: Path) -> tuple[str, str, str, str]:
    parts = trajectory_path.parts
    try:
        index = parts.index("golden-trajectory")
    except ValueError:
        if len(parts) < 4:
            raise SystemExit(f"cannot infer case from trajectory path: {trajectory_path}")
        index = len(parts) - 5
    try:
        app = parts[index + 1]
        category = parts[index + 2]
        case_number = parts[index + 3]
        path_name = parts[index + 4]
    except IndexError as exc:
        raise SystemExit(f"cannot infer case from trajectory path: {trajectory_path}") from exc
    return app, category, case_number, path_name


def _print_aggregate(title: str, rows: list[Dict[str, Any]], key_fn) -> None:
    grouped: Dict[tuple[str, ...], list[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(key_fn(row), []).append(row)

    print(title)
    print("group\tn\tMC\tEOC\tEE")
    for key, group_rows in sorted(grouped.items()):
        print(
            "\t".join(
                [
                    "/".join(key),
                    str(len(group_rows)),
                    _fmt(mean(row["mc"] for row in group_rows)),
                    _fmt(mean(row["eoc"] for row in group_rows)),
                    _fmt(mean(row["ee"] for row in group_rows)),
                ]
            )
        )
    print()


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _result_to_dict(result: Any) -> Dict[str, Any]:
    return {
        "case_id": result.case_id,
        "process_complete": result.process_complete,
        "MC": result.milestone_coverage,
        "EOC": result.evidence_order_coverage,
        "EvidenceEfficiency": result.evidence_efficiency,
        "milestone_count": result.milestone_count,
        "total_tool_calls": result.total_tool_calls,
        "evidence_tool_count": result.evidence_tool_count,
        "established": {
            milestone_id: {
                "step_index": match.step_index,
                "tool_name": match.tool_name,
                "admissible_index": match.admissible_index,
                "evidence_group_index": match.evidence_group_index,
                "manual_review_required": match.manual_review_required,
            }
            for milestone_id, match in result.established.items()
        },
        "ordered": {
            milestone_id: {
                "step_index": match.step_index,
                "tool_name": match.tool_name,
                "admissible_index": match.admissible_index,
                "evidence_group_index": match.evidence_group_index,
                "manual_review_required": match.manual_review_required,
            }
            for milestone_id, match in result.ordered.items()
        },
        "missing": list(result.missing),
        "satisfied_edges": [list(edge) for edge in result.satisfied_edges],
        "unsatisfied_edges": [list(edge) for edge in result.unsatisfied_edges],
        "manual_review_milestones": list(result.manual_review_milestones),
    }


if __name__ == "__main__":
    raise SystemExit(main())
