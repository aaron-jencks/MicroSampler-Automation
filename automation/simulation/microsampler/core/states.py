from abc import ABC
import json
import logging
import os
import re
import shutil
import subprocess as sp
from enum import StrEnum
from typing import Type, Union, Iterable

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from .defs import MicroSamplerCoreDeploymentState, MicroSamplerLoopContext
from .exceptions import (MicroSamplerSimulationError, MicroSamplerParsingError, MicroSamplerStatsError)
from ...exceptions import SubprocessError
from ...states import DeploymentState, SubprocessDeploymentState

logger = logging.getLogger(__name__)


class MicroSamplerInitialState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        ctx.context.current_key_index = 0
        ctx.context.current_app_index = 0

        if len(ctx.context.run_config.keys) == 0:
            ctx.stop(ValueError(f"expected at least one key, found zero"))
            return

        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.PREPARE)


class MicroSamplerLoopControllerState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        ctx.context.current_key_index += 1
        if ctx.context.current_key_index >= len(ctx.context.run_config.keys):
            ctx.context.current_key_index = 0
            ctx.context.current_app_index += 1

        if ctx.context.current_app_index >= len(ctx.context.run_config.apps):
            return

        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.PREPARE)


class MicroSamplerPrepareState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        deployment_prefix = self.config.microsampler.deployment_prefix
        app = ctx.context.run_config.apps[ctx.context.current_app_index]
        key = ctx.context.run_config.keys[ctx.context.current_key_index]
        ctx.context.log_prefix = deployment_prefix / "logs" / ctx.context.run_config.design / ctx.context.run_config.suite / app / str(ctx.context.run_config.iterations) / key
        ctx.context.log_prefix.mkdir(parents=True, exist_ok=True)
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.SIMULATION)


class MicroSamplerSubprocessState(SubprocessDeploymentState, ABC):
    def run_microsampler_checked_subprocess(
            self, ctx: StateContext,
            err: Type[SubprocessError], next_state: StrEnum,
            args: Union[Iterable[str], str],
            script_name: str, log_name: str,
    ):
        log_path = ctx.context.log_prefix / log_name
        self.run_checked_subprocess(
            ctx, err, next_state,
            [str((self.config.microsampler.scripts_prefix / script_name).resolve().absolute()), *args],
            stdout=log_path, stderr=sp.STDOUT,
            env_overrides={
                "SIM_ROOT": str(self.config.microsampler.working_directory.resolve().absolute()),
                "RISCV": str(self.config.microsampler.riscv_root.resolve().absolute()),
            },
            cwd=self.config.microsampler.working_directory,
        )


class MicroSamplerSimulationState(MicroSamplerSubprocessState):
    def execute(self, ctx: MicroSamplerLoopContext):
        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerSimulationError, MicroSamplerCoreDeploymentState.PARSE,
            [
                ctx.context.run_config.keys[ctx.context.current_key_index],
                ctx.context.run_config.suite,
                ctx.context.run_config.apps[ctx.context.current_app_index],
                str(ctx.context.run_config.iterations),
                ctx.context.run_config.design,
            ],
            "do_simulation.sh", "launch_simulation.log"
        )


class MicroSamplerParseState(MicroSamplerSubprocessState):
    def execute(self, ctx: MicroSamplerLoopContext):
        key = ctx.context.run_config.keys[ctx.context.current_key_index]

        args = [key]

        suite = ctx.context.run_config.suite
        app = ctx.context.run_config.apps[ctx.context.current_app_index]

        if suite == "microbench":
            if app == "ct_ccopy":
                args.extend([
                    "0x008000010e", "0x0080000124", "0x0080000196", "0x0080000130", "0x008000019a"
                ])
            else:
                ctx.stop(ValueError(f"app {app} not supported"))
                return
        elif suite == "bearssl_synthetic":
            if app == "v1":
                args.extend([
                    "0x0000010128", "0x000001012c", "0x00000106d2", "0x000001022c", "0x00000106d6"
                ])
            elif app == "v1_warmup":
                args.extend([
                    "0x000001014a", "0x000001014e", "0x00000106f4", "0x000001024e", "0x00000106f8"
                ])
            elif app == "v1_fence":
                args.extend([
                    "0x0000010128", "0x000001012c", "0x00000107a4", "0x000001022c", "0x00000107a8"
                ])
            elif app == "v2":
                args.extend([
                    "0x000001012c", "0x0000010130", "0x0000010882", "0x000001021a", "0x0000010886"
                ])
            elif app == "v2_warmup":
                args.extend([
                    "0x0000010152", "0x0000010156", "0x00000108a8", "0x0000010240", "0x00000108ac"
                ])
            elif app == "v2_fence":
                args.extend([
                    "0x000001012c", "0x0000010130", "0x000001095c", "0x000001021a", "0x0000010960"
                ])
            elif app == "v3":
                args.extend([
                    "0x0000010128", "0x000001012c", "0x000001052e", "0x000001023c", "0x0000010532"
                ])
            elif app == "v3_warmup":
                args.extend([
                    "0x000001014a", "0x000001014e", "0x0000010550", "0x000001025e", "0x0000010554"
                ])
            elif app == "v3_fence":
                args.extend([
                    "0x0000010128", "0x000001012c", "0x0000010600", "0x000001023c", "0x0000010604"
                ])
            else:
                ctx.stop(ValueError(f"app {app} not supported"))
                return
        else:
            ctx.stop(ValueError(f"suite {suite} not supported"))
            return

        args.extend([
            suite, app, str(ctx.context.run_config.iterations), ctx.context.run_config.design,
        ])

        logger.info(f"Running parsing with {args}")

        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerParsingError, MicroSamplerCoreDeploymentState.STATS,
            args,
            "do_parse.sh", "launch_parse.log"
        )


class MicroSamplerStatsState(MicroSamplerSubprocessState):
    def execute(self, ctx: MicroSamplerLoopContext):
        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerStatsError, MicroSamplerCoreDeploymentState.LOOP_CHECK,
            [
                ctx.context.run_config.keys[ctx.context.current_key_index],
                ctx.context.run_config.suite,
                ctx.context.run_config.apps[ctx.context.current_app_index],
                str(ctx.context.run_config.phi),
                str(ctx.context.run_config.alpha),
                str(ctx.context.run_config.window),
                str(ctx.context.run_config.iterations),
                ctx.context.run_config.design,
            ],
            "do_stats.sh", "launch_stats.log"
        )
