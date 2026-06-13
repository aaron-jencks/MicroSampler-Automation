import logging
import os
import re
import shutil
import subprocess as sp
from typing import List

from tqdm import tqdm

from config import BaseConfig
from simulation.exceptions import BuildError
from simulation.struct import BuildResult, RunConfiguration, RunResult


logger = logging.getLogger(__file__)


def verify_legal_code(ctx: BaseConfig, contents: str) -> bool:
    acceptable_references = set(ctx.harness.allowed_references)
    for m in re.finditer(r"#include \"(?P<filename>.*?)\"", contents):
        if m.group("filename") not in acceptable_references:
            return False
    return True


def build_harness(ctx: BaseConfig) -> BuildResult:
    harness_prefix = ctx.harness.prefix
    logger.info(f"Building harness in: {harness_prefix}")
    logger.info(f"Fetching UUT source code...")
    shutil.copy(ctx.harness.uut.prefix / ctx.harness.uut.file, harness_prefix)
    logger.info("Building harness...")
    make_output = sp.run(
        ["make", "clean", "harness"],
        capture_output=True,
        cwd=harness_prefix,
    )
    return BuildResult(
        stdout=make_output.stdout.decode(),
        stderr=make_output.stderr.decode(),
        return_code=make_output.returncode,
    )


def deploy_harness(ctx: BaseConfig, configuration: RunConfiguration) -> List[RunResult]:
    logger.info("Deploying harness...")
    build_output = build_harness(ctx)
    if build_output.return_code != 0:
        raise BuildError(build_output)
    logger.info("Staging Deployment...")
    deploy_path = ctx.harness.deployment_prefix
    os.makedirs(deploy_path, exist_ok=True)
    shutil.copy(ctx.harness.prefix / ctx.harness.executable, deploy_path)
    shutil.copy(ctx.harness.prefix / "build" / ctx.harness.assembly_file, deploy_path)
    logger.info("Running UUT...")
    result_list = []
    for iteration in tqdm(range(configuration.global_iterations), desc="Running Simulations"):
        result = RunResult(stderr=None, stdout=None, errored=False, timedout=False, return_code=0, output_files=[])
        try:
            commands = [
                f"./{ctx.harness.executable}",
                str(configuration.inner_iterations),
                str(configuration.random_seed),
            ]
            logger.debug(f"Running: {' '.join(commands)}")
            run_output = sp.run(
                commands,
                cwd=deploy_path,
                capture_output=True,
                timeout=ctx.harness.timeout
            )
            result.stderr = run_output.stderr.decode(errors="ignore")
            result.stdout = run_output.stdout.decode(errors="ignore")
            result.return_code = run_output.returncode
            result.errored = run_output.returncode != 0
            logger.debug("UUT finished.")
        except sp.TimeoutExpired:
            logger.warning("UUT timed out.")
            result.timedout = True
            result.errored = True
        result_list.append(result)
    return result_list
