from typing import Callable, Dict, List

from langchain_core.tools import BaseTool

from config import BaseConfig


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
