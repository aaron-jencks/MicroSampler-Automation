import argparse
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess as sp
from typing import List, Dict, Optional

from cascade_config import CascadeConfig
from openai import OpenAI
from pydantic import BaseModel


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RunConfiguration(BaseModel):
    attack_source: Optional[str]
    key_cases: Optional[List[str]]
    global_iterations: int
    inner_iterations: int
    have_conclusion: bool
    conclusion_reason: Optional[str]


def load_configs(cfgs: List[Path], default: Path) -> Dict:
    conf = CascadeConfig()
    conf.add_json(default)
    for cfg in cfgs:
        conf.add_json(cfg)
    return conf.parse()


@dataclass
class RunResult:
    stderr: Optional[str]
    stdout: Optional[str]
    errored: bool
    timedout: bool
    return_code: int


def deploy_harness(ctx: Dict, configuration: RunConfiguration, cls: int):
    logger.info("Building harness...")
    sp.call(["make", "clean", "harness"], cwd=ctx["harness"]["prefix"])
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
        if configuration.key_cases is not None:
            commands.append(str(deploy_path / ctx["harness"]["key_file"]))
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
        logger.info("UUT finished.")
    except sp.TimeoutExpired:
        logger.info("UUT timed out.")
        result.timedout = True
        result.errored = True
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('config', nargs='*', type=Path, help='the config files to use')
    ap.add_argument('--default-config', type=Path, default=Path('./config/default.json'), help='the default configuration file to use')
    args = ap.parse_args()

    cfg = load_configs(args.config, args.default_config)

    run_configuration = RunConfiguration(
        attack_source=None,
        key_cases=None,
        global_iterations=1,
        inner_iterations=100,
    )

    run_result = deploy_harness(cfg, run_configuration, 0)
    print(run_result)

    
