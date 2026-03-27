import argparse
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess as sp
from typing import List, Dict, Optional

from cascade_config import CascadeConfig
from openai import OpenAI
from pydantic import BaseModel


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RunConfiguration(BaseModel):
    reasoning: str
    attack_source: Optional[str]
    key_cases: Optional[List[str]]
    global_iterations: int
    inner_iterations: int
    have_conclusion: bool
    constant_time_passed: bool


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


def generate_model_instructions(ctx: Dict, template_name: str = 'input') -> str:
    with open(ctx["llm"]["templates"][template_name], 'r') as f:
        template = f.read()

    def replace_source_code(m: re.Match) -> str:
        fname = m.group('filename')

        with open(Path(ctx["harness"]["prefix"]) / fname, 'r') as f:
            source_data = f.read()

        return f"{fname}\n```\n{source_data}\n```"

    processed_template = re.sub(
        r'\[\[(?P<filename>.*?)]]',
        replace_source_code,
        template,
        flags=re.MULTILINE | re.UNICODE
    )

    return processed_template


def prompt_model(ctx: Dict, template_name: str, conversation: List[Dict[str, str]]) -> RunConfiguration:
    logger.info(f"Current message to the model is: {conversation[-1]['content']}")

    response = ctx["llm"]["client"].responses.parse(
        model=ctx["llm"]["model"],
        instructions=generate_model_instructions(ctx, template_name),
        input=conversation,
        text_format=RunConfiguration,
        # reasoning={
        #     "effort": "high"
        # }
    )

    logger.info(f"Model response: {response.output_text}")

    conversation.append({
        "role": "assistant",
        "content": response.output_text
    })

    # Check for refusal
    for item in response.output:
        if item.content is not None:
            for content in item.content:
                if content.type == "refusal":
                    raise RuntimeError(f"Model refused: {content.refusal}")

    # Safe to parse
    if response.output_parsed is None:
        raise RuntimeError("No parsed output (possibly malformed response)")

    return response.output_parsed


def handle_code_generation(ctx: Dict, history: List[Dict[str, str]], previous_config: Optional[RunConfiguration]) -> RunConfiguration:
    while True:
        model_response = prompt_model(ctx, 'input', history)

        errors = []

        # check static configuration errors
        if model_response.attack_source is None:
            if previous_config is not None and previous_config.attack_source is None:
                errors.append("There is no previous source code written, you must write source code.")
            # we don't have to assign the previous to this because the file already exists, we don't have to write it again.
        if model_response.key_cases is None:
            if previous_config is not None and previous_config.key_cases is not None:
                model_response.key_cases = previous_config.key_cases
        if model_response.global_iterations < 1:
            errors.append("There must be at least one global iteration.")
        if model_response.inner_iterations < 1:
            errors.append("There must be at least one inner iteration.")
        if model_response.reasoning == "":
            errors.append("No reasoning. Please show your work and provide reasoning and justification.")

        if model_response.have_conclusion and model_response.reasoning != "":
            return model_response  # if the model has come to a conclusion then who cares if the rest of the data is malformed

        # if we have code, see if it compiles
        compiles = False
        if model_response.attack_source is not None:
            with open(Path(ctx["harness"]["prefix"]) / ctx["harness"]["target"], 'w+') as f:
                f.write(model_response.attack_source)
            build_output = build_harness(ctx)
            if build_output.return_code != 0:
                be_string = (f"The source code build failed with exit code {build_output.return_code}:\n\n"
                             f"stdout:\n```\n{build_output.stdout}\n```\n\n"
                             f"stderr:\n```\n{build_output.stderr}\n```")
                errors.append(be_string)
            else:
                compiles = True

        if len(errors) > 0:
            e_string = "There were errors found in your response, please correct the following:\n"
            for ei, error in enumerate(errors):
                e_string += f"\n{ei + 1}. {error}"
            history.append({
                "role": "user",
                "content": e_string,
            })
            continue

        if compiles:
            return model_response


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

        gi_responses = "The code has finished running, here are the results:\n\n"
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
            gi_responses += (f"Iteration {gi} results:\n\n"
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
    cfg["llm"]["client"] = OpenAI(api_key=cfg["llm"]["api_key"])

    main(cfg)
    
