import argparse
from dataclasses import dataclass
from enum import Enum
import logging
import os
from pathlib import Path
import shutil
import subprocess as sp
from typing import List, Dict, Optional

from cascade_config import CascadeConfig
from openai import OpenAI

from prompting.client import OpenAIClient
import tools


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_configs(cfgs: List[Path], default: Path) -> Dict:
    conf = CascadeConfig()
    conf.add_json(default)
    for cfg in cfgs:
        conf.add_json(cfg)
    return conf.parse()


def setup_model_client(ctx: Dict) -> OpenAIClient:
    if ctx["llm"]["api_key"] != "":
        inner_client = OpenAI(api_key=ctx["llm"]["api_key"])
    else:
        inner_client = OpenAI()
    client = OpenAIClient(inner_client, "input")
    client.create_action(tools.WorkbenchFileCreate(ctx))
    client.create_action(tools.WorkbenchReadFile(ctx))
    client.create_action(tools.WorkbenchDeleteFile(ctx))
    client.create_action(tools.WorkbenchListFiles(ctx))
    client.create_action(tools.WorkbenchRun(ctx))
    client.create_action(tools.AttackFileCreate(ctx))
    client.create_action(tools.RunSimulation(ctx))
    return client


def main(ctx: Dict):
    logger.info(f"Using instruction prompt:\n\n{generate_model_instructions(ctx)}")

    iteration = 1
    context = [{
        "role": "developer",
        "content": "Let's get started, you'll need to generate code, test cases, everything on this first pass here."
    }]
    previous_config = None
    while True:
        logger.info(f"Starting iteration: {iteration}")
        config = handle_code_generation(ctx, context, previous_config)
        if config.have_conclusion:
            logger.info(f"The model thinks it's done!")
            logger.info("The algorithm IS constant-time" if config.constant_time_passed else "The algorithm is NOT constant-time")
            logger.info(f"Justification: {config.reasoning}")
            break
        if config.attack_source is None:
            logger.info("Using previous attacker source code")
        else:
            logger.info(f"Using new attacker source code:\n```\n{config.attack_source}\n```")
        if config.key_cases is None:
            logger.info("No key cases supplied, they must be hardcoded")
        else:
            logger.info(f"Using key cases:\n```\n{'\n'.join(config.key_cases)}\n```")
        logger.info(f"Doing {config.global_iterations} iterations")
        logger.info(f"Doing {config.inner_iterations} inner iterations")
        logger.info(f"The current model reasoning is: {config.reasoning}")

        gi_responses = "The code has finished running, here are the results:"
        errored = False
        for gi in range(config.global_iterations):
            logger.info(f"Running global iteration {gi}")
            logger.info("Running class 0")
            c0_result = deploy_harness(ctx, config, 0)
            logger.info(f"Run stderr: \n```\n{c0_result.stderr}\n```")
            if c0_result.errored:
                logger.warning("An error occurred while running deployed code")
                if c0_result.timedout:
                    logger.warning("The code timed out")
                    e_string = "There was an error while running the generated code: It timed out."
                else:
                    logger.warning("There was a runtime issue with the code")
                    e_string = (f"There was an error while running the generated code (return code {c0_result.return_code}):\n\n"
                                f"stdout:\n```\n{c0_result.stdout}\n```\n\n"
                                f"stderr:\n```\n{c0_result.stderr}\n```")
                context.append({
                    "role": "user",
                    "content": e_string,
                })
                errored = True
                break
            logger.info("Running class 1")
            c1_result = deploy_harness(ctx, config, 1)
            logger.info(f"Run stderr: \n```\n{c1_result.stderr}\n```")
            if c1_result.errored:
                logger.warning("An error occurred while running deployed code")
                if c1_result.timedout:
                    logger.warning("The code timed out")
                    e_string = "There was an error while running the generated code: It timed out."
                else:
                    logger.warning("There was a runtime issue with the code")
                    e_string = (f"There was an error while running the generated code (return code {c1_result.return_code}):\n\n"
                                f"stdout:\n```\n{c1_result.stdout}\n```\n\n"
                                f"stderr:\n```\n{c1_result.stderr}\n```")
                context.append({
                    "role": "user",
                    "content": e_string,
                })
                errored = True
                break
            logger.info("Both deployments finished, collecting data")
            gi_responses += (f"\n\nIteration {gi} results:\n\n"
                            f"Class 0:\n```\n{c0_result.stdout}\n```\n\n"
                            f"Class 1:\n```\n{c1_result.stdout}\n```")

        if not errored:
            context.append({
                "role": "user",
                "content": gi_responses,
            })
        iteration += 1
        previous_config = config


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('config', nargs='*', type=Path, help='the config files to use')
    ap.add_argument('--default-config', type=Path, default=Path('./config/default.json'), help='the default configuration file to use')
    args = ap.parse_args()

    cfg = load_configs(args.config, args.default_config)
    if cfg["llm"]["api_key"] != "":
        cfg["llm"]["client"] = OpenAI(api_key=cfg["llm"]["api_key"])
    else:
        cfg["llm"]["client"] = OpenAI()

    main(cfg)
    
