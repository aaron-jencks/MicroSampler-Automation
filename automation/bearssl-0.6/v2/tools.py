import logging
import os, sys
from pathlib import Path
import subprocess as sp
from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from prompting.actions import LLMAction, LLMActionResponse, default_action_response, LLMActionError
from building import build_harness, deploy_harness, RunConfiguration, RunResult

logger = logging.getLogger(__name__)


class ToolBaseArgs(BaseModel):
    reasoning: str = Field(description="The reason that you are executing this action")


def create_log_statement_for_tool_use(args: ToolBaseArgs, fmt: str, *fargs):
    inner_string = fmt.format(*fargs)
    logger.info(
        f"{inner_string}\n"
        f"step reasoning: {args.reasoning}"
    )


class FileNameArgs(ToolBaseArgs):
    file_name: str = Field(description="The name of the file")


class FileCreateArgs(FileNameArgs):
    file_contents: str = Field(description="The content of the file")


class WorkbenchFileCreate(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            f'workbench_create_file',
            f"creates or replaces a file in the workbench",
            FileCreateArgs
        )

    def execute(self, ctx: Dict, kwargs: FileCreateArgs) -> LLMActionResponse:
        prefix = Path(ctx['workbench']['prefix'])
        file_path = prefix / kwargs.file_name
        create_log_statement_for_tool_use(
            kwargs,
            "creating file: {} with contents:\n```\n{}\n```",
            file_path.absolute(), kwargs.file_contents
        )
        with open(file_path, mode='w+') as fp:
            fp.write(kwargs.file_contents)
        return default_action_response


class WorkbenchReadFile(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            "workbench_read_file",
            "read a file and report its contents",
            FileNameArgs
        )

    def execute(self, ctx: Dict, kwargs: FileNameArgs) -> LLMActionResponse:
        prefix = Path(ctx['workbench']['prefix'])
        file_path = prefix / kwargs.file_name
        create_log_statement_for_tool_use(
            kwargs,
            "reading file: {}",
            file_path.absolute()
        )
        if not file_path.exists():
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                f"{kwargs.file_name}"
            ))
        with open(file_path, mode='r') as fp:
            data = fp.read()
        return LLMActionResponse(data, None)


class WorkbenchDeleteFile(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            "workbench_delete_file",
            "delete a file from the workbench",
            FileNameArgs
        )

    def execute(self, ctx: Dict, kwargs: FileNameArgs) -> LLMActionResponse:
        prefix = Path(ctx['workbench']['prefix'])
        file_path = prefix / kwargs.file_name
        create_log_statement_for_tool_use(
            kwargs,
            "deleting file: {}",
            file_path.absolute()
        )
        if not file_path.exists():
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                f"{kwargs.file_name}"
            ))
        os.remove(file_path)
        return default_action_response


class WorkbenchListFiles(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            "workbench_list_files",
            "lists the names of the files currently in the workbench",
            ToolBaseArgs
        )

    def execute(self, ctx: Dict, kwargs: ToolBaseArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "listing workbench files"
        )
        prefix = Path(ctx['workbench']['prefix'])
        result = []
        for dirpath, dirnames, filenames in os.walk(prefix):
            for filename in filenames:
                result.append(str(Path(dirpath) / filename))
        return LLMActionResponse('\n'.join(result), None)


class WorkbenchRunArgs(ToolBaseArgs):
    args: List[str] = Field(description="The cli args to be passed to the shell script, "
                                        "if they would be separated by a space in the shell, "
                                        "they should be different elements.")


class WorkbenchRun(LLMAction):
    def __init__(self, ctx: Dict):
        self.script_path = Path(ctx['workbench']['workbench']) / ctx['workbench']['script']
        super().__init__(
            "workbench_run",
            f"runs the workbench script: {self.script_path}, must finish within 5 minutes",
            ToolBaseArgs
        )

    def execute(self, ctx: Dict, kwargs: WorkbenchRunArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "running workbench script"
        )
        if not self.script_path.exists():
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                str(self.script_path)
            ))
        try:
            response = sp.run(
                [str(self.script_path), *kwargs.args],
                cwd=Path(ctx['workbench']['workbench']).absolute(),
                capture_output=True,
                timeout=300
            )
        except sp.TimeoutExpired:
            return LLMActionResponse(None, LLMActionError(
                "timeout",
                "the script call exceeded 5 minutes"
            ))
        return LLMActionResponse(
            (
                f"stdout:\n```\n{response.stdout.decode()}\n```\n"
                f"stderr:\n```\n{response.stderr.decode()}\n```"
            ),
            None
        )


class AttackSourceArgs(ToolBaseArgs):
    attack_contents: str = Field(description="The contents of the attack source code")


class AttackFileCreate(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            'create_attack_file',
            'stores the source code for the attack file',
            AttackSourceArgs
        )

    def execute(self, ctx: Dict, kwargs: AttackSourceArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "writing attack code:\n```\n{}\n```",
            kwargs.attack_contents
        )
        file_name = Path(ctx['harness']['prefix']) / ctx['harness']['target']
        with open(file_name, mode='w+') as fp:
            fp.write(kwargs.attack_contents)
        build_status = build_harness(ctx)
        if build_status.return_code != 0:
            return LLMActionResponse(None, LLMActionError(
                "build failed",
                f"stdout:\n```\n{build_status.stdout}\n```\nstderr:\n```\n{build_status.stderr}\n```"
            ))
        return default_action_response


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
            "However trial_setup and trial_teardown are still called each iteration, so in that way you can reset state."
        )
    )
    run_name: str = Field(
        description=(
            "The location in the workbench to store the output json data. "
            "This will be placed in the workbench data directory. "
            "Each class will get it's own file, it will have the layout of:\n"
            "```\n"
            "data_directory/run_name\n"
            "\tclass_#.json\n"
            "```"
        )
    )
    stderr_file: Optional[str] = Field(
        description=(
            "The location in the workbench to store the stderr output. "
            "If omitted the stderr will not be logged."
        )
    )


class RunSimulation(LLMAction):
    def __init__(self, ctx: Dict):
        super().__init__(
            "run_simulation",
            f"runs the harness simulation with a timeout of {ctx['harness']['timeout']} seconds",
            SimulationArgs
        )

    def _handle_simulation_output(
            self, ctx: Dict, args: SimulationArgs, cls: int,
            output: RunResult, base_result: LLMActionResponse = None
    ) -> LLMActionResponse:
        logger.info('parsing run output')

        result = base_result if base_result is not None else LLMActionResponse(None, None)

        log_prefix = Path(ctx['workbench']['data_directory']) / args.run_name
        log_prefix.mkdir(parents=True, exist_ok=True)

        logger.info("logging stderr")
        if args.stderr_file is not None and output.stderr is not None:
            err_file = log_prefix / args.stderr_file
            with open(err_file, mode='w+') as fp:
                fp.write(output.stderr)
            if result.response_message == "":
                result.response_message = "output files:"
            result.response_message += f"\n{err_file}"
        else:
            logger.info("stderr file not supplied or not stderr output captured, skipping")

        if output.errored:
            if output.timedout:
                result.error = LLMActionError(
                    "simulation timed out",
                    f"simulation took longer than {ctx['harness']['timeout']} seconds"
                )
            else:
                result.error = LLMActionError(
                    "simulation failed",
                    f"simulation failed with code: {output.return_code}\n"
                    f"stderr:\n```\n{output.stderr}\n```",
                )
            return result

        output_file_name = log_prefix / f"class_{cls}.json"
        with open(output_file_name, mode='w+') as fp:
            fp.write(output.stdout)

        if result.response_message == "":
            result.response_message = "output files:"
        result.response_message += f"\n{output_file_name}"

        return result

    def execute(self, ctx: Dict, kwargs: SimulationArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "running harness simulation"
        )
        config = RunConfiguration(
            kwargs.global_iterations,
            kwargs.inner_iterations,
        )
        logger.info("running class 0")
        cls_0_output = deploy_harness(ctx, config, 0)
        result = self._handle_simulation_output(ctx, cls_0_output)
        if result.error is not None:
            logger.info("an error occurred during class 0, skipping class 1")
            return result
        logger.info("running class 1")
        cls_1_output = deploy_harness(ctx, config, 1)
        result = self._handle_simulation_output(ctx, cls_1_output, result)
        return result
