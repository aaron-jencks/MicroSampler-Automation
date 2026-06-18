from abc import ABC
import json
import logging
import os
import re
import shutil
import subprocess as sp

import pandas as pd
from qstate import State
from tqdm import tqdm

from config import BaseConfig
from .defs import CCopyLoopContext, CCopyDeploymentState
from .struct import BuildResult, RunResult
from ..exceptions import IllegalCodeError, BuildError, SimulationTimeoutError, SimulationFailureError


logger = logging.getLogger(__name__)


class DeploymentState(State, ABC):
    def __init__(self, ctx: BaseConfig):
        super().__init__()
        self.config = ctx

    @staticmethod
    def append_deployment_state(ctx: CCopyLoopContext, deployment_state: CCopyDeploymentState):
        ctx.queue.append(deployment_state.value)


class CCopyVerifyLegalCode(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        acceptable_references = set(self.config.harness.allowed_references)
        for m in re.finditer(r"#include \"(?P<filename>.*?)\"", ctx.context.implementation):
            if m.group("filename") not in acceptable_references:
                ctx.stop(IllegalCodeError(ctx.context.implementation))
                return
        self.append_deployment_state(ctx, CCopyDeploymentState.WRITE)


class CCopyWriteAttack(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        file_name = self.config.harness.prefix / self.config.harness.target
        with open(file_name, mode='w+') as fp:
            fp.write(ctx.context.implementation)
        self.append_deployment_state(ctx, CCopyDeploymentState.COMPILE)


class CCopyCompileHarness(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        harness_prefix = self.config.harness.prefix
        logger.info(f"Building harness in: {harness_prefix}")
        logger.info(f"Fetching UUT source code...")
        shutil.copy(self.config.harness.uut.prefix / self.config.harness.uut.file, harness_prefix)
        logger.info("Building harness...")
        make_output = sp.run(
            ["make", "clean", "harness"],
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
        self.append_deployment_state(ctx, CCopyDeploymentState.PREPARE)


class CCopyPrepareDeploymentStage(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        logger.info("Staging Deployment...")
        deploy_path = self.config.harness.deployment_prefix
        os.makedirs(deploy_path, exist_ok=True)
        shutil.copy(self.config.harness.prefix / self.config.harness.executable, deploy_path)
        shutil.copy(self.config.harness.prefix / "build" / self.config.harness.assembly_file, deploy_path)
        self.append_deployment_state(ctx, CCopyDeploymentState.RUN_FULL)


class CCopyRunSimulationIteration(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        if ctx.context.pbar is None:
            ctx.context.pbar = tqdm(total=ctx.context.configuration.global_iterations, desc="Running Simulations")

        deploy_path = self.config.harness.deployment_prefix
        result = RunResult(stderr=None, stdout=None, errored=False, timedout=False, return_code=0, output_files=[])
        try:
            commands = [
                f"./{self.config.harness.executable}",
                str(ctx.context.configuration.inner_iterations),
                str(ctx.context.configuration.random_seed),
            ]
            logger.debug(f"Running: {' '.join(commands)}")
            run_output = sp.run(
                commands,
                cwd=deploy_path,
                capture_output=True,
                timeout=self.config.harness.timeout
            )
            result.stderr = run_output.stderr.decode(errors="ignore")
            result.stdout = run_output.stdout.decode(errors="ignore")
            result.return_code = run_output.returncode
            result.errored = run_output.returncode != 0
            logger.debug("UUT finished.")
            if result.errored:
                ctx.stop(SimulationFailureError(result))
                return
        except sp.TimeoutExpired:
            logger.warning("UUT timed out.")
            result.timedout = True
            result.errored = True
            ctx.stop(SimulationTimeoutError(result, self.config.harness.timeout))
            return
        ctx.context.results.append(result)

        ctx.context.pbar.update(1)
        ctx.context.current_global_iteration += 1
        if ctx.context.current_global_iteration < ctx.context.configuration.global_iterations:
            self.append_deployment_state(ctx, CCopyDeploymentState.RUN_LOOP)
        else:
            ctx.context.pbar.close()
            self.append_deployment_state(ctx, CCopyDeploymentState.TABULATE)


class CCopyRunSimulation(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        logger.info("Running UUT...")
        ctx.context.results.clear()
        self.append_deployment_state(ctx, CCopyDeploymentState.RUN_LOOP)


class CCopyTabulateResults(DeploymentState):
    def execute(self, ctx: CCopyLoopContext):
        logger.info('parsing run output')

        output_rows = []

        for iteration in range(ctx.context.configuration.global_iterations):
            output = ctx.context.results[iteration]
            raw_data = json.loads(output.stdout)
            seed = raw_data["seed"]
            for row in raw_data["data"]:
                inner_iteration = row["iteration"]
                for bit_data in row["durations"]:
                    output_rows.append({
                        'run_name': ctx.context.configuration.run_name,
                        'random_seed': seed,
                        'global_iteration': iteration,
                        'inner_iteration': inner_iteration,
                        **bit_data
                    })

        ctx.context.final_table = pd.DataFrame(output_rows)
