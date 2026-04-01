from pathlib import Path
from typing import Dict, List

from prompting.client import OpenAIClient


def template_insert_file(ctx: Dict, tag_name: str, args: List[str]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


def add_default_template_tools_to_client(ctx: Dict, client: OpenAIClient):
    client.create_template_tool("source", template_insert_file)
