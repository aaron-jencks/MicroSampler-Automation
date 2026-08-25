from abc import ABC
import logging
from pathlib import Path
import subprocess as sp
from enum import StrEnum
from typing import Callable, List, Optional, Tuple, Type

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from config import BaseConfig
from .defs import MicroSamplerCoreDeploymentState, MicroSamplerLoopContext
from .exceptions import (MicroSamplerSimulationError, MicroSamplerParsingError, MicroSamplerStatsError,
                         MicroSamplerPCParsingError)
from ..exceptions import UnknownSuiteError
from ..pc_finder import find_pcs
from .script_replacements import do_simulation, do_parse, do_stats, SubprocessArguments, load_key_value
from ...states import DeploymentState
from tools import SubprocessError

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
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.FIND_PCS)


class MicroSamplerFindPCsState(DeploymentState):
    def execute(self, ctx: MicroSamplerLoopContext):
        logger.debug("starting microsampler PC finder step")
        pc_config = ctx.context.run_config.pc_config
        pcs = find_pcs(pc_config.obj_file, pc_config.roi_function, pc_config.uut_function, pc_config.warmup)
        if pcs is None:
            ctx.stop(MicroSamplerPCParsingError(pc_config))
            return
        logger.debug(f"found pcs: {pcs}")
        ctx.context.pc_addresses = pcs
        self.append_deployment_state(ctx, MicroSamplerCoreDeploymentState.SIMULATION)


CoreMicroSamplerStepFunc = Callable[[BaseConfig, SubprocessArguments], Optional[sp.CompletedProcess]]


class MicroSamplerCoreStepState(DeploymentState, ABC):
    def __init__(self, ctx: BaseConfig, sp_timeout: Optional[float] = None):
        super().__init__(ctx)
        self.sp_timeout = sp_timeout

    def get_builtin_executable_path_w_args(self, ctx: StateContext) -> Tuple[Path, List[str]]:
        full_app = ctx.context.run_config.apps[ctx.context.current_app_index]
        suite = ctx.context.run_config.suite
        key = ctx.context.run_config.keys[ctx.context.current_key_index]
        iterations = ctx.context.run_config.iterations

        if "_" in full_app:
            short_app, app_type = full_app.split("_")
        else:
            short_app = full_app
            app_type = ""

        app_prefix = self.config.microsampler.working_directory / "apps"
        if suite.startswith("bearssl"):
            app_prefix /= "bearssl-0.6"
            if suite == "bearssl_synthetic":
                app_prefix /= "microsampler_tests"
            app_prefix /= "build"
        elif suite == "openssl":
            raise NotImplementedError("openssl requires access to home directory which is unaccessible")
        elif suite == "microbench":
            app_prefix = app_prefix / "microbench" / full_app / key
        else:
            raise UnknownSuiteError(suite)

        args = []
        keyval = load_key_value(self.config, key)
        if suite == "bearssl_comb":
            if app_type == "warmup":
                executable = app_prefix / "testcrypto_warmup"
            else:
                executable = app_prefix / "testcrypto"
            args.extend([short_app, keyval, iterations])
        elif suite == "bearssl_single":
            executable = app_prefix / f"testcrypto_{full_app}"
            args.append(keyval)
        elif suite == "bearssl_synthetic":
            executable = app_prefix / full_app
            args.extend([keyval, iterations])
        elif suite == "microbench":
            executable = app_prefix / full_app
        else:
            raise UnknownSuiteError(suite)

        return executable, args

    def generate_subprocess_args(
            self, ctx: StateContext, log_name: str,
            executable: Optional[Path], executable_args: Optional[List[str]]
    ) -> SubprocessArguments:
        app = ctx.context.run_config.apps[ctx.context.current_app_index]
        key = ctx.context.run_config.keys[ctx.context.current_key_index]
        design = ctx.context.run_config.design
        iterations = ctx.context.run_config.iterations
        suite = ctx.context.run_config.suite
        return SubprocessArguments(
            log_prefix=ctx.context.log_prefix,
            log_name=log_name,
            executable=executable,
            executable_args=executable_args,
            key=key,
            suite=suite,
            app=app,
            phi=ctx.context.run_config.phi,
            alpha=ctx.context.run_config.alpha,
            window=ctx.context.run_config.window,
            design=design,
            iterations=iterations,
            pc_addresses=ctx.context.pc_addresses,
            timeout=self.sp_timeout
        )

    def run_microsampler_checked_subprocess(
            self, ctx: StateContext,
            err: Type[SubprocessError], next_state: StrEnum,
            log_name: str,
            func: CoreMicroSamplerStepFunc,
            executable: Optional[Path] = None,
            executable_args: Optional[List[str]] = None,
            need_executable: bool = True
    ):
        if need_executable:
            if executable_args is None:
                executable_args = []
            if executable is None:
                executable, exec_args = self.get_builtin_executable_path_w_args(ctx)
                executable_args.extend(exec_args)

        args = self.generate_subprocess_args(ctx, log_name, executable, executable_args)

        res = func(self.config, args)
        if res is not None and res.returncode != 0:
            raise err(res.returncode, res.stdout, res.stderr)

        self.append_deployment_state(ctx, next_state)


class MicroSamplerSimulationState(MicroSamplerCoreStepState):
    def __init__(self, ctx: BaseConfig, sp_timeout: Optional[float] = None,
                 next_state: StrEnum = MicroSamplerCoreDeploymentState.PARSE):
        super().__init__(ctx, sp_timeout)
        self.next_state = next_state

    def execute(self, ctx: MicroSamplerLoopContext):
        logger.debug("starting microsampler simulation")
        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerSimulationError, self.next_state,
            "launch_simulation.log", do_simulation,
            ctx.context.run_config.executable,
            ctx.context.run_config.executable_args,
        )


class MicroSamplerParseState(MicroSamplerCoreStepState):
    def __init__(self, ctx: BaseConfig, sp_timeout: Optional[float] = None,
                 next_state: StrEnum = MicroSamplerCoreDeploymentState.STATS):
        super().__init__(ctx, sp_timeout)
        self.next_state = next_state

    def execute(self, ctx: MicroSamplerLoopContext):
        logger.debug("starting microsampler parse")

        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerParsingError, self.next_state,
            "launch_parse.log", do_parse,
            need_executable=False,
        )


class MicroSamplerStatsState(MicroSamplerCoreStepState):
    def __init__(self, ctx: BaseConfig, sp_timeout: Optional[float] = None,
                 next_state: StrEnum = MicroSamplerCoreDeploymentState.LOOP_CHECK):
        super().__init__(ctx, sp_timeout)
        self.next_state = next_state

    def execute(self, ctx: MicroSamplerLoopContext):
        logger.debug("starting microsampler stats execution")
        self.run_microsampler_checked_subprocess(
            ctx, MicroSamplerStatsError, self.next_state,
            "launch_stats.log", do_stats,
            need_executable=False,
        )
