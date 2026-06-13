from pathlib import Path
from typing import Callable, Dict, List

from langchain_core.tools import BaseTool, tool

from config import BaseConfig


class MissingAttackAssemblyError(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(
            f"attack assembly is missing at {path}; deployment should have generated it before summarization"
        )


ToolFactory = Callable[[BaseConfig], BaseTool]


class AgentToolRegistry:
    def __init__(self):
        self._factories: Dict[str, ToolFactory] = {}

    def register(self, name: str, factory: ToolFactory):
        self._factories[name] = factory

    def create_tools(self, ctx: BaseConfig, names: List[str]) -> List[BaseTool]:
        tools: List[BaseTool] = []
        for name in names:
            if name not in self._factories:
                raise ValueError(f"unknown agent tool: {name}")
            tools.append(self._factories[name](ctx))
        return tools


def create_read_attack_assembly_tool(ctx: BaseConfig) -> BaseTool:
    @tool
    def read_attack_assembly() -> str:
        """Read the deployed attack.s assembly for the latest deployed attack implementation."""
        path = ctx.harness.deployment_prefix / ctx.harness.assembly_file
        if not path.exists():
            raise MissingAttackAssemblyError(path)
        assembly = path.read_text(errors="replace")
        return f"Assembly path: {path}\n\n{assembly}"

    return read_attack_assembly


def create_default_agent_tool_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register("read_attack_assembly", create_read_attack_assembly_tool)
    return registry
