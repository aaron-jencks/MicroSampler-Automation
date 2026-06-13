from typing import Callable, Dict, List

from langchain_core.tools import BaseTool

from agents.defs import GovernorContext
from config import BaseConfig
from reporting.logger import ReportLog

ToolFactory = Callable[[BaseConfig, GovernorContext, ReportLog, str], BaseTool]


class AgentToolRegistry:
    def __init__(self, ctx: BaseConfig, q_state: GovernorContext, reporter: ReportLog):
        self._factories: Dict[str, ToolFactory] = {}
        self._ctx = ctx
        self._governor_state = q_state
        self._reporter = reporter

    def register(self, name: str, factory: ToolFactory):
        self._factories[name] = factory

    def create_tools(self, names: List[str]) -> List[BaseTool]:
        tools: List[BaseTool] = []
        for name in names:
            if name not in self._factories:
                raise ValueError(f"unknown agent tool: {name}")
            tools.append(self._factories[name](self._ctx, self._governor_state, self._reporter, name))
        return tools
