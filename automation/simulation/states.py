from abc import ABC
from enum import StrEnum
import subprocess as sp
from typing import Type

from qstate import State, StateContext

from config import BaseConfig
from .exceptions import SubprocessError


class DeploymentState(State, ABC):
    def __init__(self, ctx: BaseConfig):
        super().__init__()
        self.config = ctx

    def append_deployment_state(self, ctx: StateContext, state: StrEnum):
        ctx.queue.append(state.value)

    def check_subprocess_output(
            self, ctx: StateContext, sp_output: sp.CompletedProcess,
            err: Type[SubprocessError], next_state: StrEnum
    ):
        if sp_output.returncode != 0:
            ctx.stop(err(sp_output.returncode, sp_output.stdout, sp_output.stderr))
        else:
            self.append_deployment_state(ctx, next_state)