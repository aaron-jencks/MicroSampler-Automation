from abc import ABC
from enum import StrEnum

from qstate import State, StateContext

from config import BaseConfig


class DeploymentState(State, ABC):
    def __init__(self, ctx: BaseConfig):
        super().__init__()
        self.config = ctx

    @staticmethod
    def append_deployment_state(ctx: StateContext, state: StrEnum):
        ctx.queue.append(state.value)