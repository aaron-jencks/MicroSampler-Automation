import logging
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


logger = logging.getLogger(__name__)


class ToolBaseArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str = Field(description="The reason that you are executing this action")


def create_log_statement_for_tool_use(args: ToolBaseArgs, fmt: str, *fargs):
    inner_string = fmt.format(*fargs)
    logger.info(
        f"{inner_string}\n"
        f"step reasoning: {args.reasoning}"
    )


class BugReportArgs(ToolBaseArgs):
    bug: str = Field(description="The description of the bug that you are reporting")


class SuggestionBoxArgs(ToolBaseArgs):
    suggestion: str = Field(description="The description of the suggestion that you are submitting")


class FileNameArgs(ToolBaseArgs):
    file_name: str = Field(description="The name of the file")


class FileCreateArgs(FileNameArgs):
    file_contents: str = Field(description="The content of the file")


class WorkbenchRunArgs(ToolBaseArgs):
    args: List[str] = Field(description="The cli args to be passed to the shell script, "
                                        "if they would be separated by a space in the shell, "
                                        "they should be different elements.")


class ResetWorkbenchArgs(ToolBaseArgs):
    flush_data: bool = Field(
        description="whether to delete the cached simulation run data or not"
    )


class AttackSourceArgs(ToolBaseArgs):
    attack_contents: str = Field(description="The contents of the attack source code")


class SimulationArgs(ToolBaseArgs):
    global_iterations: int = Field(
        description=(
            "The number of times to run the simulation while resetting the state each time. "
            "Think of it like we're resetting the microarchitectural state each time."
        )
    )
    inner_iterations: int = Field(
        description=(
            "The number of times to run the simulation without resetting the state. "
            "Think of it like there's a loop between global_setup and global_teardown. "
            "The global state is not reset between iterations. "
            "However trial_setup and trial_teardown are still called each iteration, "
            "so in that way you can reset state."
        )
    )
    random_seed: int = Field(
        description=(
            "The random seed for reproducibility purposes."
        )
    )
    run_name: str = Field(
        description=(
            "The location in the workbench to store the output json data. "
            "This will be placed in the workbench data directory. "
            "Each class will get it's own file, it will have the layout of:\n"
            "```\n"
            "data_directory/[run_name]\n"
            "\tdata-{global_iteration}.json\n"
            "```"
        )
    )
    stderr_file: Optional[str] = Field(
        description=(
            "The location in the workbench to store the stderr output. "
            "If omitted the stderr will not be logged. "
            "The error file will be place in:\n"
            "```\n"
            "data_directory/[run_name]\n"
            "\t[stderr_file]-{global_iteration}\n"
            "```"
        )
    )


class ConclusionArgs(ToolBaseArgs):
    constant_time: bool = Field(
        description="True if you think the algorithm is constant time, False otherwise, "
                    "support for this conclusion must be in your reasoning",
    )
