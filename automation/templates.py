import logging
from pathlib import Path
from typing import Any, Dict, List

from prompting.templates import TemplateController

logger = logging.getLogger(__name__)


def template_insert_file(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Dict[str, Any]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


def template_insert_template(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Dict[str, Any]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(ctx["llm"]["templates"]["files"][args[0]])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    processed_template = client.process_template(ctx, data)
    return processed_template


def template_insert_config_value(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Dict[str, Any]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = ctx
    for key in args:
        current = current[key]
    return repr(current)


def template_insert_allowed_references(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Dict[str, Any]) -> str:
    result = []
    for reference in ctx["harness"]["allowed_references"]:
        result.append(f"- {reference}")
    return '\n'.join(result)


def template_insert_runtime_data(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Dict[str, Any]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = kwargs
    for key in args:
        current = current[key]
    return repr(current)


def add_default_template_tools_to_client(ctx: Dict, client: TemplateController):
    client.create_template_tool("source", template_insert_file)
    client.create_template_tool("template", template_insert_template)
    client.create_template_tool("config", template_insert_config_value)
    client.create_template_tool("allowed_references", template_insert_allowed_references)
    client.create_template_tool("runtime_data", template_insert_runtime_data)
