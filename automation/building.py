from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess as sp
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class RunConfiguration:
    global_iterations: int
    inner_iterations: int
    run_name: str
    random_seed: int


@dataclass
class RunResult:
    stdout: Optional[str]
    stderr: Optional[str]
    output_files: Optional[List[str]]
    errored: bool
    timedout: bool
    return_code: int


@dataclass
class BuildResult:
    stdout: Optional[str]
    stderr: Optional[str]
    return_code: int


def verify_legal_code(ctx: Dict, contents: str) -> bool:
    acceptable_references = set(ctx["harness"]["allowed_references"])
    for m in re.finditer(r"#include \"(?P<filename>.*?)\"", contents):
        if m.group("filename") not in acceptable_references:
            return False
    return True


def build_harness(ctx: Dict) -> BuildResult:
    make_output = sp.run(
        ["make", "clean", "harness"],
        capture_output=True,
        cwd=Path(ctx["general_prefix"]) / ctx["harness"]["prefix"]
    )
    return BuildResult(
        stdout=make_output.stdout.decode(),
        stderr=make_output.stderr.decode(),
        return_code=make_output.returncode,
    )


def deploy_harness(ctx: Dict, configuration: RunConfiguration) -> List[RunResult]:
    logger.info("Building harness...")
    build_output = build_harness(ctx)
    if build_output.return_code != 0:
        logger.error(f"Build harness failed with code {build_output.return_code}:\nstderr: {build_output.stderr}\nstdout: {build_output.stdout}")
        return [RunResult(
            stderr=build_output.stderr,
            stdout=build_output.stdout,
            errored=True,
            timedout=False,
            return_code=build_output.return_code,
            output_files=[],
        )]
    logger.info("Staging Deployment...")
    deploy_path = Path(ctx["general_prefix"]) / ctx["harness"]["deployment_prefix"]
    os.makedirs(deploy_path, exist_ok=True)
    shutil.copy(Path(ctx["general_prefix"]) / ctx["harness"]["prefix"] / ctx["harness"]["executable"], deploy_path)
    logger.info("Running UUT...")
    result_list = []
    for iteration in range(configuration.global_iterations):
        result = RunResult(stderr=None, stdout=None, errored=False, timedout=False, return_code=0, output_files=[])
        try:
            commands = [
                f"./{ctx['harness']['executable']} {configuration.inner_iterations} {configuration.random_seed}",
            ]
            logger.info(f"Running: {' '.join(commands)}")
            run_output = sp.run(
                commands,
                cwd=deploy_path,
                capture_output=True,
                timeout=ctx["harness"]["timeout"],
                shell=True
            )
            result.stderr = run_output.stderr.decode(errors="ignore")
            result.stdout = run_output.stdout.decode(errors="ignore")
            result.return_code = run_output.returncode
            result.errored = run_output.returncode != 0
            logger.info("UUT finished.")
        except sp.TimeoutExpired:
            logger.info("UUT timed out.")
            result.timedout = True
            result.errored = True
        result_list.append(result)
    return result_list
