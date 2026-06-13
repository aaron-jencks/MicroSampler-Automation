from pathlib import Path

from langchain_core.tools import BaseTool, tool

from agents.defs import GovernorContext
from config import BaseConfig
from prompting.tools import AgentToolRegistry
from reporting.default.events import ToolCallEvent
from reporting.logger import ReportLog


class MissingAttackAssemblyError(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(
            f"attack assembly is missing at {path}; deployment should have generated it before summarization"
        )


def create_read_attack_assembly_tool(
        ctx: BaseConfig, state_context: GovernorContext, reporter: ReportLog,
        name: str
) -> BaseTool:
    @tool
    def read_attack_assembly() -> str:
        """Read the deployed attack.s assembly for the latest deployed attack implementation."""
        reporter.log(ToolCallEvent(state_context.iteration, name))
        path = ctx.harness.deployment_prefix / ctx.harness.assembly_file
        if not path.exists():
            raise MissingAttackAssemblyError(path)
        assembly = path.read_text(errors="replace")
        return f"Assembly path: {path}\n\n{assembly}"

    return read_attack_assembly


def create_default_agent_tool_registry(ctx: BaseConfig, q_state: GovernorContext, reporter: ReportLog) -> AgentToolRegistry:
    registry = AgentToolRegistry(ctx, q_state, reporter)
    registry.register("read_attack_assembly", create_read_attack_assembly_tool)
    return registry
