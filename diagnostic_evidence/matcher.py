from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, Iterable, Mapping, Optional

from .schema import AdmissibleToolUse, EvidencePattern, ToolCall


_RESOURCE_ALIASES = {
    "pod": "pods",
    "pods": "pods",
    "po": "pods",
    "svc": "services",
    "service": "services",
    "services": "services",
    "ep": "endpoints",
    "endpoint": "endpoints",
    "endpoints": "endpoints",
    "deploy": "deployments",
    "deployment": "deployments",
    "deployments": "deployments",
    "rs": "replicasets",
    "replicaset": "replicasets",
    "replicasets": "replicasets",
    "node": "nodes",
    "nodes": "nodes",
    "event": "events",
    "events": "events",
    "pv": "persistentvolumes",
    "persistentvolume": "persistentvolumes",
    "persistentvolumes": "persistentvolumes",
    "pvc": "persistentvolumeclaims",
    "persistentvolumeclaim": "persistentvolumeclaims",
    "persistentvolumeclaims": "persistentvolumeclaims",
}


def observation_to_text(observation: Any) -> str:
    if isinstance(observation, str):
        return observation
    return json.dumps(observation, ensure_ascii=False, sort_keys=True)


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(text)
        except Exception:
            pass
    return value


def parse_cache_key(key: str) -> ToolCall:
    if ":" not in key:
        return ToolCall(tool_name=key, arguments={}, raw=key)
    tool_name, raw_args = key.split(":", 1)
    try:
        args = json.loads(raw_args)
    except Exception:
        args = {}
    return ToolCall(tool_name=tool_name, arguments=args, raw=key)


def parse_golden_calling(calling: str, fallback_tool_name: str = "") -> ToolCall:
    tool_match = re.search(r"tool_name=['\"]([^'\"]+)['\"]", calling)
    tool_name = tool_match.group(1) if tool_match else fallback_tool_name
    args_match = re.search(r"arguments=\{(.*)\}\s*$", calling)
    if not args_match:
        return ToolCall(tool_name=tool_name, arguments={}, raw=calling)

    raw_args = args_match.group(1)
    args: Dict[str, Any] = {}
    for key, raw_value in _split_argument_items(raw_args):
        args[key] = _parse_argument_value(raw_value)
    return ToolCall(tool_name=tool_name, arguments=args, raw=calling)


def _split_argument_items(raw_args: str) -> Iterable[tuple[str, str]]:
    current = []
    quote: Optional[str] = None
    depth = 0
    for char in raw_args:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                yield _split_key_value(item)
            current = []
        else:
            current.append(char)
    item = "".join(current).strip()
    if item:
        yield _split_key_value(item)


def _split_key_value(item: str) -> tuple[str, str]:
    if ":" not in item:
        return item.strip(), ""
    key, value = item.split(":", 1)
    return key.strip().strip("'\""), value.strip()


def _parse_argument_value(value: str) -> Any:
    if value in {"None", "null"}:
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return ast.literal_eval(value)
    except Exception:
        return value.strip("'\"")


def tool_use_matches(call: ToolCall, admissible: AdmissibleToolUse) -> bool:
    if call.tool_name != admissible.tool_name:
        return False
    for expected_key, expected_value in admissible.arguments.items():
        if expected_key not in call.arguments:
            return False
        if not _argument_value_matches(call.arguments[expected_key], expected_value):
            return False
    return True


def _argument_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_argument_value_matches(actual, item) for item in expected)
    if actual == expected:
        return True
    actual_norm = _normalize_arg_value(actual)
    expected_norm = _normalize_arg_value(expected)
    return actual_norm == expected_norm


def _normalize_arg_value(value: Any) -> Any:
    if isinstance(value, str):
        return _RESOURCE_ALIASES.get(value, value)
    return value


def pattern_matches(pattern: EvidencePattern, observation: Any) -> bool:
    text = observation_to_text(observation)
    kind = pattern.kind
    if kind == "literal":
        return _literal_matches(str(pattern.value), text, pattern.flags)
    if kind == "regex":
        return re.search(str(pattern.value), text, _regex_flags(pattern.flags)) is not None
    if kind == "json_path":
        return _json_path_matches(pattern, observation)
    if kind == "yaml_path":
        return _yaml_path_matches(pattern, text)
    if kind == "code_snippet":
        return _code_snippet_matches(str(pattern.value), text)
    raise ValueError(f"Unsupported evidence pattern kind: {kind}")


def _literal_matches(needle: str, haystack: str, flags: Iterable[str]) -> bool:
    if "case_sensitive" in flags:
        return needle in haystack
    return needle.casefold() in haystack.casefold()


def _regex_flags(flags: Iterable[str]) -> int:
    compiled = re.DOTALL
    if "case_sensitive" not in flags:
        compiled |= re.IGNORECASE
    if "multiline" in flags:
        compiled |= re.MULTILINE
    return compiled


def _json_path_matches(pattern: EvidencePattern, observation: Any) -> bool:
    obj = parse_jsonish(observation)
    if isinstance(obj, str):
        return False
    value = _read_path(obj, pattern.path or str(pattern.value))
    if value is _MISSING:
        return False
    if pattern.equals is not None:
        return value == pattern.equals
    if pattern.contains is not None:
        if isinstance(value, (list, tuple, set)):
            return pattern.contains in value
        return str(pattern.contains).casefold() in observation_to_text(value).casefold()
    return bool(value)


_MISSING = object()


def _read_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list):
            if part == "*":
                return current
            try:
                current = current[int(part)]
            except Exception:
                return _MISSING
        else:
            return _MISSING
    return current


def _yaml_path_matches(pattern: EvidencePattern, text: str) -> bool:
    # PyYAML is intentionally not required. For Kubernetes YAML observations,
    # path matching falls back to nearby key/value textual evidence.
    expected_path = pattern.path or str(pattern.value)
    expected_leaf = expected_path.split(".")[-1]
    expected_value = pattern.equals if pattern.equals is not None else pattern.contains
    if expected_value is None:
        return re.search(rf"^\s*{re.escape(expected_leaf)}\s*:", text, re.MULTILINE) is not None
    return re.search(
        rf"^\s*{re.escape(expected_leaf)}\s*:\s*['\"]?{re.escape(str(expected_value))}['\"]?\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    ) is not None


def _code_snippet_matches(snippet: str, text: str) -> bool:
    return _squash_whitespace(snippet) in _squash_whitespace(text)


def _squash_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
