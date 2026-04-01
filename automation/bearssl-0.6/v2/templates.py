import logging
from pathlib import Path
from typing import Dict, List, Type

from pydantic import BaseModel

from prompting.client import OpenAIClient
from prompting.actions import LLMAction


logger = logging.getLogger(__name__)


def template_insert_file(ctx: Dict, client: OpenAIClient, tag_name: str, args: List[str]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


def model_to_readable_doc(action: LLMAction) -> str:
    model = action.schema
    schema = model.model_json_schema()
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    lines = [f"{action.name}: {action.description}"]

    for name, field in props.items():
        field_type = field.get("type", "any")
        desc = field.get("description", "")
        is_required = "required" if name in required else "optional"

        lines.append(f"- {name} ({field_type}, {is_required}): {desc}")

    return "\n".join(lines)


def template_insert_schema(ctx: Dict, client: OpenAIClient, tag_name: str, args: List[str]) -> str:
    logger.debug(f"creating schema documentation for {tag_name} with arguments {args}")
    entries = []
    if len(args) > 0:
        for action in args:
            if action not in client.tools:
                raise RuntimeError(f"Action {action} not found in client tools")
            entries.append(model_to_readable_doc(client.tools[action]))
    else:
        for action in client.tools.keys():
            entries.append(model_to_readable_doc(client.tools[action]))

    return "\n\n".join(entries)


def template_insert_template(ctx: Dict, client: OpenAIClient, tag_name: str, args: List[str]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    processed_template = client.generate_preprocessed_template(ctx, data)
    return processed_template


def template_insert_config_value(ctx: Dict, client: OpenAIClient, tag_name: str, args: List[str]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = ctx
    for key in args:
        current = current[key]
    return current


def add_default_template_tools_to_client(ctx: Dict, client: OpenAIClient):
    client.create_template_tool("source", template_insert_file)
    client.create_template_tool("schema", template_insert_schema)
    client.create_template_tool("template", template_insert_template)
    client.create_template_tool("config", template_insert_config_value)
