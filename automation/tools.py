import logging
import os
from pathlib import Path
import subprocess as sp
from typing import Any, Dict, IO, Iterable, Optional, Type, Union

from langchain_core.tools import BaseTool, tool

from agents.defs import GovernorContext
from config import BaseConfig
from prompting.tools import AgentToolRegistry
from reporting.default.events import ToolCallEvent
from reporting.logger import ReportLog


logger = logging.getLogger(__name__)


def get_path(p: Path) -> str:
    return str(p.resolve().absolute())


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


PROC_OUTPUT = Optional[Union[str, Path]]


class SubprocessError(Exception):
    def __init__(self, code: int, stdout: PROC_OUTPUT = None, stderr: PROC_OUTPUT = None, *args: Any):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        if len(args) > 0:
            super().__init__(*args)
        else:
            super().__init__(f"subprocess failed with code {self.code}")

    def format_error(self) -> str:
        stdout = self.stdout
        if isinstance(self.stdout, Path):
            stdout = self.stdout.read_text()
        stderr = self.stderr
        if isinstance(self.stderr, Path):
            stderr = self.stderr.read_text()
        return f"""Return code: {self.code}
        Stdout:
        {stdout}

        Stderr:
        {stderr}
        """


SP_FILE = Optional[Union[IO[Any], int, Path]]


def run_subprocess(
        args: Union[Iterable[str], str],
        stdin: SP_FILE = None,
        stdout: SP_FILE = None,
        stderr: SP_FILE = None,
        shell: bool = False,
        env_overrides: Optional[Dict[str, str]] = None,
        inherit_env: bool = True,
        check_output: bool = False,
        cwd: Optional[Path] = None,
        timeout: Optional[float] = None
) -> sp.CompletedProcess:
    env = os.environ.copy() if inherit_env else {}
    if env_overrides:
        env.update(env_overrides)
    csi, cso, cse = False, False, False
    logging_statement = f"running subprocess:\n{args}"
    if isinstance(stdin, Path):
        logging_statement += f"\n\tusing stdin: {stdin}"
        stdin = open(stdin, 'r')
        csi = True
    if isinstance(stdout, Path):
        logging_statement += f"\n\tusing stdout: {stdout}"
        stdout = open(stdout, 'w+')
        cso = True
    if isinstance(stderr, Path):
        logging_statement += f"\n\tusing stderr: {stderr}"
        stderr = open(stderr, 'w+')
        cse = True
    if cwd is not None:
        logging_statement += f"\n\tusing cwd: {cwd}"
    if timeout is not None:
        logging_statement += f"\n\tusing timeout: {timeout} secs"
    logger.debug(logging_statement)
    try:
        sp_out = sp.run(
            args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            shell=shell,
            check=check_output,
            env=env,
            cwd=cwd,
            timeout=timeout
        )

    except sp.TimeoutExpired:
        print("\n=== SUBPROCESS TIMEOUT ===", flush=True)
        print(f"timeout = {timeout} seconds", flush=True)
        print(f"args    = {args}", flush=True)
        print(f"cwd     = {cwd}", flush=True)
        print(f"RISCV   = {env.get('RISCV')}", flush=True)
        print(f"SIM_ROOT= {env.get('SIM_ROOT')}", flush=True)
        print("==========================\n", flush=True)
        raise

    finally:
        if csi:
            stdin.close()
        if cso:
            stdout.close()
        if cse:
            stderr.close()
    return sp_out


def run_default_subprocess(
        ctx: BaseConfig,
        args: Union[Iterable[str], str],
        stdin: SP_FILE = None,
        stdout: SP_FILE = None,
        stderr: SP_FILE = None,
        shell: bool = False,
        env_overrides: Optional[Dict[str, str]] = None,
        inherit_env: bool = True,
        check_output: bool = False,
        cwd: Optional[Path] = None,
        timeout: Optional[float] = None
) -> sp.CompletedProcess:
    if env_overrides is None:
        env_overrides = {}
    env_overrides["SIM_ROOT"] = get_path(ctx.microsampler.working_directory)
    env_overrides["RISCV"] = get_path(ctx.microsampler.riscv_root)
    if cwd is None:
        cwd = ctx.microsampler.working_directory

    print("\n=== MICROSAMPLER SUBPROCESS ===", flush=True)
    print(f"args       = {args}", flush=True)
    print(f"cwd        = {cwd}", flush=True)
    print(f"SIM_ROOT   = {env_overrides.get('SIM_ROOT')}", flush=True)
    print(f"RISCV      = {env_overrides.get('RISCV')}", flush=True)
    print(f"timeout    = {timeout}", flush=True)
    print("===============================\n", flush=True)

    return run_subprocess(
        args,
        stdin, stdout, stderr,
        shell,
        env_overrides, inherit_env,
        check_output,
        cwd,
        timeout
    )
