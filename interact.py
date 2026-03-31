import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, Optional, get_args, get_origin


CURRENT_DIR = Path(__file__).resolve().parent
AGENT_ROOT = CURRENT_DIR / "cloudops_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from tools.adapters import call_tool
from tools.definition import create_k8s_tools


BENCHMARK_ROOT = CURRENT_DIR / "benchmark"
SYSTEM_ALIASES = {
    "boutique": "boutique",
    "onlineboutique": "boutique",
    "online-boutique": "boutique",
    "trainticket": "train-ticket",
    "train-ticket": "train-ticket",
}


def safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def normalize_system_name(system: str) -> str:
    key = str(system or "").strip().lower()
    if key in SYSTEM_ALIASES:
        return SYSTEM_ALIASES[key]
    raise ValueError(f"Unsupported system: {system}")


def benchmark_system_dir(system: str) -> str:
    return "trainticket" if system == "train-ticket" else system


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_random_case(system: str, fault_category: str) -> Path:
    case_root = BENCHMARK_ROOT / benchmark_system_dir(system) / fault_category
    if not case_root.is_dir():
        raise FileNotFoundError(f"Case directory not found: {case_root}")

    case_dirs = sorted(path for path in case_root.iterdir() if path.is_dir())
    if not case_dirs:
        raise ValueError(f"No cases found under: {case_root}")

    return random.choice(case_dirs)


def parse_cli_args() -> tuple[str, str]:
    if len(sys.argv) >= 3:
        return sys.argv[1], sys.argv[2]

    system = safe_input("Enter system (boutique / trainticket): ").strip()
    fault_category = safe_input("Enter fault_category: ").strip()
    return system, fault_category


def format_result(result: Any) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False, indent=2)
    text = str(result)
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception:
        return text


def is_bool_annotation(annotation: Any) -> bool:
    return annotation is bool


def is_int_annotation(annotation: Any) -> bool:
    return annotation is int


def literal_options(annotation: Any) -> list[Any]:
    origin = get_origin(annotation)
    if str(origin).endswith("Literal"):
        return list(get_args(annotation))
    return []


def prompt_for_field(
    field_name: str,
    field_info: Any,
    default_namespace: str,
) -> Optional[Any]:
    required = field_info.is_required()
    annotation = getattr(field_info, "annotation", None)
    description = (field_info.description or "").strip()
    options = literal_options(annotation)

    if field_name == "namespace":
        prompt = f"Enter {field_name}"
        if description:
            prompt += f" ({description})"
        prompt += ": "
        while True:
            value = safe_input(prompt).strip()
            if value:
                return value
            print(f"{field_name} is required. Please try again.")

    if options:
        print(f"Allowed values for {field_name}: {', '.join(map(str, options))}")
        while True:
            value = safe_input(f"Enter {field_name}: ").strip()
            if not value and not required:
                return None
            if value in {str(option) for option in options}:
                return value
            print("Input is not in the allowed values. Please try again.")

    if is_bool_annotation(annotation):
        prompt = f"Enter {field_name} (y/n, default n): "
        value = safe_input(prompt).strip().lower()
        return value in {"y", "yes", "true", "1"}

    if is_int_annotation(annotation):
        while True:
            value = safe_input(f"Enter {field_name}: ").strip()
            if not value and not required:
                return None
            try:
                return int(value)
            except ValueError:
                print("Please enter an integer.")

    prompt = f"Enter {field_name}"
    if description:
        prompt += f" ({description})"
    prompt += ": " if required else " (optional, press Enter to skip): "

    while True:
        value = safe_input(prompt).strip()
        if value:
            return value
        if not required:
            return None
        print(f"{field_name} is required. Please try again.")


def collect_tool_args(tool: Any, default_namespace: str) -> Dict[str, Any]:
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None or not hasattr(args_schema, "model_fields"):
        return {}

    args: Dict[str, Any] = {}
    for field_name, field_info in args_schema.model_fields.items():
        value = prompt_for_field(field_name, field_info, default_namespace)
        if value is not None:
            args[field_name] = value
    return args


def print_case_intro(case_path: Path, metadata: Dict[str, Any]) -> None:
    print("=" * 80)
    print("Cloud-OpsBench Interactive Demo")
    print("=" * 80)
    print(f"Random Case      : {case_path.name}")
    print(f"Namespace        : {metadata.get('namespace', '')}")
    print(f"Reported Symptom : {metadata.get('query', '')}")
    print("-" * 80)
    print("You can call tools repeatedly to investigate the case.")
    print("Choose 'Submit Diagnosis and View Ground Truth' to reveal the ground-truth answer for this case.")
    print("=" * 80)


def print_tool_menu(tools: list[Any]) -> None:
    print("\nAvailable Tools:")
    for idx, tool in enumerate(tools, 1):
        print(f"{idx}. {tool.name} - {tool.description}")
    print(f"{len(tools) + 1}. Submit Diagnosis and View Ground Truth")
    print(f"{len(tools) + 2}. Exit")


def main() -> None:
    try:
        raw_system, fault_category = parse_cli_args()
        system = normalize_system_name(raw_system)
        if not fault_category.strip():
            raise ValueError("fault_category cannot be empty")

        case_path = pick_random_case(system, fault_category.strip())
        metadata = load_json(case_path / "metadata.json")
        namespace = metadata.get("namespace", "train-ticket" if system == "train-ticket" else "boutique")
        tools = create_k8s_tools(str(case_path), system=system)

        print_case_intro(case_path, metadata)

        while True:
            print_tool_menu(tools)
            choice_text = safe_input("Select an option: ").strip()
            if not choice_text:
                print("Input ended. Exiting.")
                return

            try:
                choice = int(choice_text)
            except ValueError:
                print("Please enter a valid number.")
                continue

            if choice == len(tools) + 1:
                print("\nGround Truth")
                print("-" * 80)
                print(json.dumps(metadata.get("result", {}), ensure_ascii=False, indent=2))
                print("-" * 80)
                return

            if choice == len(tools) + 2:
                print("Exited.")
                return

            if not (1 <= choice <= len(tools)):
                print("Invalid choice. Please try again.")
                continue

            tool = tools[choice - 1]
            print(f"\nCurrent tool: {tool.name}")
            args = collect_tool_args(tool, namespace)
            try:
                result = call_tool(tool, args)
            except Exception as exc:
                print(f"\nTool call error: {exc}")
                continue

            print("\nTool Result")
            print("-" * 80)
            print(format_result(result))
            print("-" * 80)

    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
