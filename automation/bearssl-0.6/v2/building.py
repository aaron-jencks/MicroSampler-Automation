from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess as sp
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class RunConfiguration:
    global_iterations: int
    inner_iterations: int
    run_name: str


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


def build_harness(ctx: Dict) -> BuildResult:
    make_output = sp.run(
        ["make", "clean", "harness"],
        capture_output=True,
        cwd=ctx["harness"]["prefix"]
    )
    return BuildResult(
        stdout=make_output.stdout.decode(),
        stderr=make_output.stderr.decode(),
        return_code=make_output.returncode,
    )


def store_output_data(ctx: Dict, run_name: str, data: str, cls: int) -> Path:
    output_file = Path(ctx['workbench']['data_directory']) / run_name / f"class_{cls}.json"
    logger.info(f"Storing {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w+') as f:
        f.write(data)
    return output_file


def deploy_harness(ctx: Dict, configuration: RunConfiguration, cls: int) -> RunResult:
    logger.info("Building harness...")
    build_output = build_harness(ctx)
    if build_output.return_code != 0:
        logger.error(f"Build harness failed with code {build_output.return_code}:\nstderr: {build_output.stderr}\nstdout: {build_output.stdout}")
        return RunResult(
            stderr=build_output.stderr,
            stdout=build_output.stdout,
            errored=True,
            timedout=False,
            return_code=build_output.return_code,
        )
    logger.info("Staging Deployment...")
    deploy_path = Path(ctx["harness"]["deployment_prefix"])
    os.makedirs(deploy_path, exist_ok=True)
    shutil.copy(Path(ctx["harness"]["prefix"]) / ctx["harness"]["executable"], deploy_path)
    if configuration.key_cases is not None:
        logger.info("Generating Key File...")
        with open(deploy_path / ctx["harness"]["key_file"], 'w+') as f:
            contents = '\n'.join(configuration.key_cases)
            f.write(contents)
    logger.info("Running UUT...")
    result = RunResult(stderr=None, stdout=None, errored=False, timedout=False, return_code=0)
    try:
        commands = [
            f"./{ctx['harness']['executable']}",
            str(cls),
            str(configuration.inner_iterations),
        ]
        logger.info(f"Running: {' '.join(commands)}")
        run_output = sp.run(
            commands,
            cwd=deploy_path,
            capture_output=True,
            timeout=ctx["harness"]["timeout"],
            shell=True
        )
        result.stderr = run_output.stderr.decode()
        result.stdout = run_output.stdout.decode()
        result.return_code = run_output.returncode
        result.errored = run_output.returncode != 0
        if not result.errored:
            result.output_files = [
                store_output_data(ctx, configuration.run_name, cls)
            ]
        logger.info("UUT finished.")
    except sp.TimeoutExpired:
        logger.info("UUT timed out.")
        result.timedout = True
        result.errored = True
    return result


def setup_workbench(ctx: Dict):
    pass