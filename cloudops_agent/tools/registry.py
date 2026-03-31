from __future__ import annotations

from typing import Any, Dict, List, get_args, get_origin

from pydantic import BaseModel


def build_tool_registry(tools_list: List[Any]) -> Dict[str, Any]:
    """Build a name -> tool object registry."""
    registry: Dict[str, Any] = {}

    for tool in tools_list:
        tool_name = getattr(tool, "name", None)

        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError(f"Invalid tool without a usable name: {tool}")

        if tool_name in registry:
            raise ValueError(f"Duplicate tool name detected: {tool_name}")

        registry[tool_name] = tool

    return registry


def render_tools_description(tool_registry: Dict[str, Any], max_desc_chars: int = 10000) -> str:
    """
    Render prompt-ready tool descriptions including argument schema.

    This is critical for helping the model produce valid Action Input JSON.
    """
    lines: List[str] = []

    for tool_name, tool_obj in tool_registry.items():
        description = getattr(tool_obj, "description", "")
        description = description.strip() if isinstance(description, str) else ""
        if len(description) > max_desc_chars:
            description = description[:max_desc_chars].rstrip() + "..."

        lines.append(f"- Tool: {tool_name}")
        if description:
            lines.append(f"  Description: {description}")

        args_schema = getattr(tool_obj, "args_schema", None)
        if args_schema is None:
            lines.append("  Parameters: {} (this tool takes no parameters; Action Input must be {})")
        else:
            lines.append("  Parameters:")
            lines.extend(_render_args_schema(args_schema))

        lines.append("")  # blank line between tools

    return "\n".join(lines).strip()


def _render_args_schema(schema_cls: type[BaseModel]) -> List[str]:
    """
    Render a Pydantic schema class into readable prompt text.
    Supports Pydantic v2 primarily; has a light fallback for v1-style access.
    """
    lines: List[str] = []

    # Pydantic v2
    model_fields = getattr(schema_cls, "model_fields", None)
    if model_fields:
        for field_name, field_info in model_fields.items():
            required = field_info.is_required()
            annotation = getattr(field_info, "annotation", None)
            type_desc = _format_annotation(annotation)

            desc = field_info.description or ""
            desc = " ".join(desc.split()) if desc else ""

            lines.append(
                f"    - {field_name} ({'required' if required else 'optional'}, {type_desc})"
                + (f": {desc}" if desc else "")
            )
        return lines

    # Pydantic v1 fallback
    legacy_fields = getattr(schema_cls, "__fields__", None)
    if legacy_fields:
        for field_name, field_info in legacy_fields.items():
            required = getattr(field_info, "required", False)
            annotation = getattr(field_info, "outer_type_", None)
            type_desc = _format_annotation(annotation)

            desc = getattr(field_info.field_info, "description", "") or ""
            desc = " ".join(desc.split()) if desc else ""

            lines.append(
                f"    - {field_name} ({'required' if required else 'optional'}, {type_desc})"
                + (f": {desc}" if desc else "")
            )
        return lines

    lines.append("    - [Could not inspect args_schema]")
    return lines


def _format_annotation(annotation: Any) -> str:
    """
    Format Python / typing annotations for prompt readability.
    Especially useful for Literal[...] constraints.
    """
    if annotation is None:
        return "unknown"

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is None:
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation)

    if str(origin).endswith("Literal"):
        values = ", ".join(repr(v) for v in args)
        return f"enum[{values}]"

    if origin in (list, List):
        inner = _format_annotation(args[0]) if args else "Any"
        return f"list[{inner}]"

    if str(origin).endswith("Union"):
        inner = ", ".join(_format_annotation(a) for a in args)
        return f"union[{inner}]"

    return str(annotation)
