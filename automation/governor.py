import argparse
import datetime as dt
import logging
from pathlib import Path
from typing import List, Dict

from cascade_config import CascadeConfig
from openai import OpenAI

from reporting.default import create_default_report_sections
from reporting.logger import ReportLog
from prompting.client import OpenAIClient
from templates import add_default_template_tools_to_client
from tools.defs import add_default_tools_to_client
from workbench import reset_workbench


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_logging(ctx: Dict):
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    )

    log_path = Path(ctx["general_prefix"]) / ctx["logging"]["prefix"] / ctx["logging"]["output"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = log_path.with_stem(log_path.stem + "_" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))

    file = logging.FileHandler(log_path)
    file.setLevel(logging.DEBUG)
    file.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file)


def load_configs(cfgs: List[Path], default: Path) -> Dict:
    conf = CascadeConfig()
    conf.add_json(default)
    for cfg in cfgs:
        conf.add_json(cfg)
    return conf.parse()


def setup_model_client(ctx: Dict, reporter: ReportLog) -> OpenAIClient:
    if ctx["llm"]["api_key"] != "":
        inner_client = OpenAI(api_key=ctx["llm"]["api_key"])
    else:
        inner_client = OpenAI()
    client = OpenAIClient(inner_client, "instructions", reporter)
    add_default_tools_to_client(ctx, client, reporter)
    add_default_template_tools_to_client(ctx, client)
    return client


def main(ctx: Dict, dry: bool = False):
    reset_workbench(ctx, True)

    reporter = ReportLog()
    create_default_report_sections(ctx, reporter)

    client = setup_model_client(ctx, reporter)
    if dry:
        client.dry_run = True

    logger.info(f"using instruction prompt:\n\n{client.load_model_template(ctx)}")

    with open(Path(ctx["general_prefix"]) / ctx["llm"]["templates"]["prefix"] / ctx["llm"]["templates"]["initial_message"], 'r') as fp:
        current_message = client.generate_preprocessed_template(ctx, fp.read())

    logger.info("starting prompting loop...")
    iteration = 1
    conclusion = None
    while True:
        logger.info("starting prompting iteration {}".format(iteration))

        responses = client.prompt_model(ctx, current_message)
        if dry:
            logger.info("dry run requested, exiting...")
            return
        if len(responses) == 0:
            logger.warning("llm didn't do anything")
            with open(Path(ctx["general_prefix"]) / ctx["llm"]["templates"]["prefix"] / ctx["llm"]["templates"]["stuck_message"], 'r') as fp:
                current_message = client.generate_preprocessed_template(ctx, fp.read())
            continue

        tool_responses = []
        messages = []
        errors = []
        for item_ctx, response in responses:
            msg_body = {
                "type": "function_call_output",
                "call_id": item_ctx.call_id,
                "output": ""
            }
            item_ctx_str = f"{item_ctx.name}"
            message_string = ""
            error_string = ""
            if response.error is not None:
                error_string = f"{response.error.name}: {response.error.description}"
            if response.conclusion is not None:
                conclusion = response.conclusion
                break
            if response.response_message is not None:
                message_string = f"{item_ctx_str}:\n\n{response.response_message}"
            if response.error is None and response.response_message is None:
                message_string = "No output"
            if message_string != "":
                msg_body["output"] = f"Output:\n\n{message_string}"
                messages.append(f"{item_ctx_str}: {message_string}")
            if error_string != "":
                if message_string != "":
                    msg_body["output"] += "\n\n"
                msg_body["output"] += f"Error:\n\n{error_string}"
                errors.append(f"{item_ctx_str}: {error_string}")
            tool_responses.append(msg_body)

        if conclusion is not None:
            break

        current_message = tool_responses
        iteration += 1

    logger.info(f"Conclusion: the algorithm {'is' if conclusion.constant_time else 'is NOT'} constant-time")
    logger.info(f"Reasoning: {conclusion.reasoning}")
    reporter.generate_report(ctx)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('config', nargs='*', type=Path, help='the config files to use')
    ap.add_argument('--default-config', type=Path, default=Path('./config/default.json'), help='the default configuration file to use')
    ap.add_argument("--dry-run", action="store_true", help='indicates to exit after generating the first prompts')
    ap.add_argument('--run-name', type=str, default=None, help='the name of the run to use, overrides the one in the config file')
    args = ap.parse_args()

    cfg = load_configs(args.config, args.default_config)
    if args.run_name is not None:
        cfg['final_report']['run_name'] = args.run_name

    setup_logging(cfg)
    main(cfg, args.dry_run)
    
