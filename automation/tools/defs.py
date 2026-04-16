import logging
from pathlib import Path
import subprocess as sp
from typing import Dict, Optional

from building import build_harness, deploy_harness, RunConfiguration, verify_legal_code
from prompting.actions import LLMAction, LLMActionResponse, default_action_response, LLMActionError, LLMConclusion
from prompting.client import OpenAIClient
from reporting import ReportLog
from simulation_utils import handle_simulation_output
from tools.args import (AttackSourceArgs, BugReportArgs, ConclusionArgs, create_log_statement_for_tool_use,
                        FileCreateArgs, FileNameArgs, ResetWorkbenchArgs, SimulationArgs, SuggestionBoxArgs,
                        ToolBaseArgs, WorkbenchRunArgs)
from workbench import (reset_workbench, create_workbench_file, delete_workbench_file, run_workbench,
                       read_workbench_file, list_workbench_files, handle_workbench_filename, get_workbench_path)

logger = logging.getLogger(__name__)


class BugReport(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "bug_report",
            "reports an identified bug for immediate developer attention, this can be something as simple as a json formatting error",
            BugReportArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: BugReportArgs) -> Optional[str]:
        return f"reported a bug: {kwargs.bug}"

    def body(self, ctx: Dict, kwargs: BugReportArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "the model thinks there's a bug in the code: {}",
            kwargs.bug
        )
        resp = input("Is this a real bug (y/N)? ").lower()
        if resp == '' or resp == 'n':
            return LLMActionResponse("this is not a valid bug, please keep working", None, None)
        elif resp == 'y':
            return LLMActionResponse(None, None, LLMConclusion(
                False,
                "There is a bug in the code, please fix it and try again",
            ))


class SuggestionBox(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "suggestion_box",
            "use this to indicate something that could be done to make your process more efficient, will be reviewed by the developer",
            SuggestionBoxArgs,
            reporter
        )

    def body(self, ctx: Dict, kwargs: SuggestionBoxArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "submitting suggestion: {}",
            kwargs.suggestion
        )
        self.reporter.log_suggestion(kwargs.suggestion)
        return default_action_response


class WorkbenchFileCreate(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            f'workbench_create_file',
            f"creates or replaces a file in the workbench",
            FileCreateArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: FileCreateArgs) -> Optional[str]:
        return f"created a workbench file: {kwargs.file_name}"

    def body(self, ctx: Dict, kwargs: FileCreateArgs) -> LLMActionResponse:
        file_path = handle_workbench_filename(ctx, kwargs.file_name)
        create_log_statement_for_tool_use(
            kwargs,
            "creating file: {} with contents:\n```\n{}\n```",
            file_path.absolute(), kwargs.file_contents
        )
        create_workbench_file(ctx, kwargs.file_name, kwargs.file_contents)
        return default_action_response


class WorkbenchReadFile(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "workbench_read_file",
            "read a file and report its contents",
            FileNameArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: FileNameArgs) -> Optional[str]:
        return f"read a workbench file: {kwargs.file_name}"

    def body(self, ctx: Dict, kwargs: FileNameArgs) -> LLMActionResponse:
        file_path = handle_workbench_filename(ctx, kwargs.file_name)
        create_log_statement_for_tool_use(
            kwargs,
            "reading file: {}",
            file_path.absolute()
        )
        try:
            data = read_workbench_file(ctx, kwargs.file_name)
            return LLMActionResponse(data, None, None)
        except FileNotFoundError:
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                f"{kwargs.file_name}"
            ), None)


class WorkbenchDeleteFile(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "workbench_delete_file",
            "delete a file from the workbench",
            FileNameArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: FileNameArgs) -> Optional[str]:
        return f"deleted a workbench file: {kwargs.file_name}"

    def body(self, ctx: Dict, kwargs: FileNameArgs) -> LLMActionResponse:
        file_path = handle_workbench_filename(ctx, kwargs.file_name)
        create_log_statement_for_tool_use(
            kwargs,
            "deleting file: {}",
            file_path.absolute()
        )
        try:
            delete_workbench_file(ctx, kwargs.file_name)
            return default_action_response
        except FileNotFoundError:
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                f"{kwargs.file_name}"
            ), None)


class WorkbenchListFiles(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "workbench_list_files",
            "lists the names of the files currently in the workbench",
            ToolBaseArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: ToolBaseArgs) -> Optional[str]:
        return "listed the workbench files"

    def body(self, ctx: Dict, kwargs: ToolBaseArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "listing workbench files"
        )
        result = list_workbench_files(ctx)
        return LLMActionResponse('\n'.join(result), None, None)


class WorkbenchRun(LLMAction):
    def __init__(self, ctx: Dict, reporter: ReportLog):
        self.script_path = get_workbench_path(ctx) / ctx['workbench']['script']
        super().__init__(
            "workbench_run",
            f"runs the workbench script: {self.script_path}, must finish within 5 minutes",
            WorkbenchRunArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: WorkbenchRunArgs) -> Optional[str]:
        return f"ran the workbench: {kwargs.args}"

    def body(self, ctx: Dict, kwargs: WorkbenchRunArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "running workbench script"
        )
        try:
            response = run_workbench(ctx, kwargs.args)
            return LLMActionResponse(
                (
                    f"stdout:\n```\n{response.stdout.decode()}\n```\n"
                    f"stderr:\n```\n{response.stderr.decode()}\n```"
                ),
                None, None
            )
        except FileNotFoundError:
            return LLMActionResponse(None, LLMActionError(
                "file not found",
                str(self.script_path)
            ), None)
        except sp.TimeoutExpired:
            return LLMActionResponse(None, LLMActionError(
                "timeout",
                "the script call exceeded 5 minutes"
            ), None)


class WorkbenchReset(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "workbench_reset",
            "resets the workbench to its original state, "
            "removing all files and resetting all imported sources.",
            ResetWorkbenchArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: ToolBaseArgs) -> Optional[str]:
        return "reset the workbench"

    def body(self, ctx: Dict, kwargs: ResetWorkbenchArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "resetting workbench files {} the data files",
            "including" if kwargs.flush_data else "excluding"
        )
        reset_workbench(ctx, data=kwargs.flush_data)
        return default_action_response


class AttackFileCreate(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            'create_attack_file',
            'stores the source code for the attack file',
            AttackSourceArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: AttackSourceArgs) -> Optional[str]:
        return f"modified the attack source code:\n```\n{kwargs.attack_contents}\n```"

    def body(self, ctx: Dict, kwargs: AttackSourceArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "writing attack code:\n```\n{}\n```",
            kwargs.attack_contents
        )
        if not verify_legal_code(ctx, kwargs.attack_contents):
            return LLMActionResponse(None, LLMActionError(
                "illegal attack code", (
                "the attack code you wrote does not pass preliminary validation "
                "you may have unallowed local references."
            )), None)
        file_name = Path(ctx["general_prefix"]) / ctx['harness']['prefix'] / ctx['harness']['target']
        with open(file_name, mode='w+') as fp:
            fp.write(kwargs.attack_contents)
        build_status = build_harness(ctx)
        if build_status.return_code != 0:
            return LLMActionResponse(None, LLMActionError(
                "build failed",
                f"stdout:\n```\n{build_status.stdout}\n```\nstderr:\n```\n{build_status.stderr}\n```"
            ), None)
        return default_action_response


class RunSimulation(LLMAction):
    def __init__(self, ctx: Dict, reporter: ReportLog):
        super().__init__(
            "run_simulation",
            f"runs the harness simulation with a timeout of {ctx['harness']['timeout']} seconds",
            SimulationArgs,
            reporter
        )

    def format_report_transcript_line(self, ctx: Dict, kwargs: SimulationArgs) -> Optional[str]:
        lines = [
            f'global iterations: {kwargs.global_iterations}',
            f'inner iterations: {kwargs.inner_iterations}',
            f'random seed: {kwargs.random_seed}',
            f'run name: "{kwargs.run_name}"',
        ]
        return f"ran simulation:\n\t" + '\n\t'.join(lines)

    def body(self, ctx: Dict, kwargs: SimulationArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "running harness simulation"
        )
        config = RunConfiguration(
            kwargs.global_iterations,
            kwargs.inner_iterations,
            kwargs.run_name,
            kwargs.random_seed,
        )
        run_outputs = deploy_harness(ctx, config)
        result = handle_simulation_output(ctx, kwargs, run_outputs)
        return result


class MakeConclusion(LLMAction):
    def __init__(self, reporter: ReportLog):
        super().__init__(
            "make_conclusion",
            "indicates that all analysis is done and that this is your final conclusion",
            ConclusionArgs,
            reporter
        )

    def body(self, ctx: Dict, kwargs: ConclusionArgs) -> LLMActionResponse:
        create_log_statement_for_tool_use(
            kwargs,
            "the LLM has come to a conclusion that the model {} constant-time",
            "is" if kwargs.constant_time is True else "is NOT",
        )
        return LLMActionResponse(None, None, LLMConclusion(
            kwargs.constant_time,
            kwargs.reasoning
        ))


def add_default_tools_to_client(ctx: Dict, client: OpenAIClient, reporter: ReportLog):
    client.create_action(WorkbenchFileCreate(reporter))
    client.create_action(WorkbenchReadFile(reporter))
    client.create_action(WorkbenchDeleteFile(reporter))
    client.create_action(WorkbenchListFiles(reporter))
    client.create_action(WorkbenchRun(ctx, reporter))
    client.create_action(WorkbenchReset(reporter))
    client.create_action(AttackFileCreate(reporter))
    client.create_action(RunSimulation(ctx, reporter))
    client.create_action(MakeConclusion(reporter))
    client.create_action(BugReport(reporter))
    client.create_action(SuggestionBox(reporter))
