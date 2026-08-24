from abc import ABC
from datetime import datetime, UTC
import logging
from pathlib import Path
import random
import re
import shutil
import subprocess as sp
from enum import StrEnum
from typing import Callable, List, Optional, Tuple, Type
import uuid

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from config import BaseConfig
from .defs import MicroSamplerTCDeploymentState, MicroSamplerTCLoopContext
from .exceptions import BuildError, IllegalCodeError
from ...states import DeploymentState
from .struct import BuildResult
from tools import SubprocessError

logger = logging.getLogger(__name__)


class MicroSamplerTCInitialState(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        ctx.context.current_key_index = 0
        ctx.context.current_app_index = 0

        if len(ctx.context.run_config.keys) == 0:
            ctx.stop(ValueError(f"expected at least one key, found zero"))
            return

        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.PREPARE)


class MicroSamplerTCPrepareState(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        ctx.context.current_global_iteration = 0
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.HARNESS_VERIFY)


class MicroSamplerTCVerifyLegalCode(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        acceptable_references = set(self.config.harness.allowed_references)
        for m in re.finditer(r"#include \"(?P<filename>.*?)\"", ctx.context.implementation):
            if m.group("filename") not in acceptable_references:
                ctx.stop(IllegalCodeError(ctx.context.implementation))
                return
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.HARNESS_PREPARE)


class MicroSamplerTCWriteAttack(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        file_name = self.config.harness.prefix / self.config.harness.target
        with open(file_name, mode='w+') as fp:
            fp.write(ctx.context.implementation)
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.HARNESS_COMPILE)


class MicroSamplerTCCompileHarness(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        harness_prefix = self.config.harness.prefix
        logger.info(f"Building harness in: {harness_prefix}")
        logger.info(f"Fetching UUT source code...")
        shutil.copy(self.config.harness.uut.prefix / self.config.harness.uut.file, harness_prefix)
        logger.info("Building harness...")
        args = ["make", "clean", "harness", *self.config.harness.make_defines]
        logger.debug(f"running make with args: {args}")
        make_output = sp.run(
            args,
            capture_output=True,
            cwd=harness_prefix,
        )
        ctx.context.build_status = BuildResult(
            stdout=make_output.stdout.decode(),
            stderr=make_output.stderr.decode(),
            return_code=make_output.returncode,
        )
        if ctx.context.build_status.return_code != 0:
            ctx.stop(BuildError(ctx.context.build_status))
            return
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.DEPLOYMENT_PREPARE)


class MicroSamplerTCPrepareKeyStage(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        # Generate 256-byte key and store it as a file in scripts/keys/something.key
        key_string = ""
        for _ in range(ctx.context.run_config.key_size):
            c = random.randint(0, 15)
            if c > 9:
                c = chr(ord('a') + c)
            key_string += str(c)
        key_name = f"{datetime.now(tz=UTC).strftime('%Y-%m-%dT%H-%M-%S-%f')}_{ctx.context.run_config.run_name}"
        # TODO save key to file
        ctx.context.current_key_name = key_name
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.MICROSAMPLER_DEPLOYMENT)
        pass


class MicroSamplerTCPrepareDeploymentStage(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        logger.info("Staging Deployment...")
        deploy_path = self.config.harness.deployment_prefix
        deploy_path.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.config.harness.prefix / self.config.harness.executable, deploy_path)
        shutil.copy(self.config.harness.prefix / "build" / self.config.harness.assembly_file, deploy_path)
        ctx.context.run_config.executable = deploy_path / self.config.harness.executable
        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.KEY_PREPARE)


class MicroSamplerTCLoopControllerState(DeploymentState):
    def execute(self, ctx: MicroSamplerTCLoopContext):
        ctx.context.current_global_iteration += 1

        if ctx.context.current_global_iteration >= ctx.context.run_config.global_iterations:
            return

        self.append_deployment_state(ctx, MicroSamplerTCDeploymentState.KEY_PREPARE)


# TODO Actual MicroSampler Deployment