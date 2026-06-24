import json
import logging
import os
import re
import shutil
import subprocess as sp

import pandas as pd
from tqdm import tqdm

from .defs import MicroSamplerCoreDeploymentState, MicroSamplerLoopContext
from ...states import DeploymentState

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
        ctx.context.log_prefix = deployment_prefix / "logs" / ctx.context.run_config.design / app / str(ctx.context.run_config.iterations) / key
        ctx.context.log_prefix.mkdir(parents=True, exist_ok=True)
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.SIMULATION)


class MicroSamplerSimulationState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        with open(ctx.context.log_prefix / "launch_simulation.log", "w+") as fp:
            sp.run(
                [
                    str((self.config.microsampler.scripts_prefix / "do_simulation.sh").resolve().absolute()),
                    ctx.context.run_config.keys[ctx.context.current_key_index],
                    ctx.context.run_config.suite,
                    ctx.context.run_config.apps[ctx.context.current_app_index],
                    str(ctx.context.run_config.iterations),
                    ctx.context.run_config.design,
                ],
                stdout=fp,
                stderr=sp.STDOUT,
            )
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.PARSE)


class MicroSamplerParseState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        args = [
            str((self.config.microsampler.scripts_prefix / "do_parse.sh").resolve().absolute()),
        ]

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

        args.extend([
            suite, app, str(ctx.context.run_config.iterations), ctx.context.run_config.design,
        ])

        with open(ctx.context.log_prefix / "launch_parse.log", "w+") as fp:
            sp.run(args, stdout=fp, stderr=sp.STDOUT)

        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.STATS)


class MicroSamplerStatsState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        with open(ctx.context.log_prefix / "launch_stats.log", "w+") as fp:
            sp.run([
                str((self.config.microsampler.scripts_prefix / "do_stats.sh").resolve().absolute()),
                ctx.context.run_config.keys[ctx.context.current_key_index],
                ctx.context.run_config.suite,
                ctx.context.run_config.apps[ctx.context.current_app_index],
                str(ctx.context.run_config.phi),
                str(ctx.context.run_config.alpha),
                str(ctx.context.run_config.window),
                str(ctx.context.run_config.iterations),
                ctx.context.run_config.design,
            ], stdout=fp, stderr=sp.STDOUT)
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.LOOP_CHECK)
