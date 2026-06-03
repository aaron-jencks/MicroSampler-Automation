import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, get_origin, get_args

from pydantic import BaseModel

from agents import Hypothesis, Implementation, Summarization
from prompting.templates import TemplateController

logger = logging.getLogger(__name__)


def template_insert_file(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


def template_insert_template(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(ctx["llm"]["templates"]["files"][args[0]])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    processed_template = client.process_template(ctx, data)
    return processed_template


def template_insert_config_value(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = ctx
    for key in args:
        current = current[key]
    return repr(current)


def template_insert_allowed_references(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    result = []
    for reference in ctx["harness"]["allowed_references"]:
        result.append(f"- {reference}")
    return '\n'.join(result)


def template_insert_runtime_data(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = kwargs
    for key in args:
        current = current[key]
    return repr(current)


def format_type(t) -> str:
    origin = get_origin(t)

    if origin is None:
        return getattr(t, "__name__", str(t))

    if origin is list:
        return f"list[{format_type(get_args(t)[0])}]"

    if origin is dict:
        k, v = get_args(t)
        return f"dict[{format_type(k)}, {format_type(v)}]"

    return str(t)


def describe_model(model: type[BaseModel]) -> str:
    lines = [f"{model.__name__}:"]

    for name, field in model.model_fields.items():
        required = "required" if field.is_required() else "optional"

        desc = ""
        if field.description:
            desc = f" - {field.description}"

        lines.append(
            f"  - {name}: {format_type(field.annotation)} ({required}){desc}"
        )

    return "\n".join(lines)


model_map = {
    "hypothesis": Hypothesis,
    "implementation": Implementation,
    "summary": Summarization,
}


def template_insert_model(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    return describe_model(model_map[args[0]])



def add_default_template_tools_to_client(ctx: Dict, client: TemplateController):
    client.create_template_tool("source", template_insert_file)
    client.create_template_tool("template", template_insert_template)
    client.create_template_tool("config", template_insert_config_value)
    client.create_template_tool("allowed_references", template_insert_allowed_references)
    client.create_template_tool("runtime_data", template_insert_runtime_data)
    client.create_template_tool("model", template_insert_model)
