from abc import ABC
from enum import StrEnum
import logging
import os
from pathlib import Path
import subprocess as sp
from typing import Any, Dict, Iterable, Optional, Type, Union, IO

from qstate import State, StateContext

from config import BaseConfig
from .exceptions import SubprocessError


logger = logging.getLogger(__name__)


class DeploymentState(State, ABC):
    def __init__(self, ctx: BaseConfig):
        super().__init__()
        self.config = ctx

    def append_deployment_state(self, ctx: StateContext, state: StrEnum):
        ctx.queue.append(state.value)


SP_FILE = Optional[Union[IO[Any], int, Path]]


class SubprocessDeploymentState(DeploymentState, ABC):
    def check_subprocess_output(
            self, ctx: StateContext, sp_output: sp.CompletedProcess,
            err: Type[SubprocessError], next_state: StrEnum,
            stdout: Optional[Path] = None, stderr: Optional[Path] = None
    ):
        if sp_output.returncode != 0:
            e = err(
                sp_output.returncode,
                stdout if stdout else sp_output.stdout,
                stderr if stderr else sp_output.stderr
            )
            logger.warning(f"subprocess failed, program output:\n\n{e.format_error()}")
            ctx.stop(e)
        else:
            self.append_deployment_state(ctx, next_state)

    def run_subprocess(
            self,
            args: Union[Iterable[str], str],
            stdin: SP_FILE = None,
            stdout: SP_FILE = None,
            stderr: SP_FILE = None,
            shell: bool = False,
            env_overrides: Optional[Dict[str, str]] = None,
            inherit_env: bool = True,
            check_output: bool = False,
            cwd: Optional[Path] = None
    ) -> sp.CompletedProcess:
        env = os.environ.copy() if inherit_env else {}
        if env_overrides:
            env.update(env_overrides)
        csi, cso, cse = False, False, False
        if isinstance(stdin, Path):
            stdin = open(stdin, 'r')
            csi = True
        if isinstance(stdout, Path):
            stdout = open(stdout, 'w+')
            cso = True
        if isinstance(stderr, Path):
            stderr = open(stderr, 'w+')
            cse = True
        try:
            sp_out = sp.run(
                args,
                stdin=stdin, stdout=stdout, stderr=stderr,
                shell=shell, check=check_output,
                env=env, cwd=cwd
            )
        finally:
            if csi:
                stdin.close()
            if cso:
                stdout.close()
            if cse:
                stderr.close()
        return sp_out

    def run_checked_subprocess(
            self, ctx: StateContext,
            err: Type[SubprocessError], next_state: StrEnum,
            args: Union[Iterable[str], str],
            stdin: SP_FILE = None,
            stdout: SP_FILE = None,
            stderr: SP_FILE = None,
            shell: bool = False,
            env_overrides: Optional[Dict[str, str]] = None,
            inherit_env: bool = True,
            cwd: Optional[Path] = None
    ):
        run_out = self.run_subprocess(
            args, stdin, stdout, stderr, shell, env_overrides, inherit_env, False, cwd
        )
        self.check_subprocess_output(
            ctx, run_out, err, next_state,
            stdout=stdout if isinstance(stdout, Path) else None, stderr=stderr if isinstance(stderr, Path) else None
        )
