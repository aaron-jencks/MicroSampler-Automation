import argparse
import logging
from pathlib import Path
from typing import List, Dict

from cascade_config import CascadeConfig
from openai import OpenAI

from prompting.client import OpenAIClient
from templates import add_default_template_tools_to_client
from tools import add_default_tools_to_client


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
    add_default_tools_to_client(ctx, client)
    add_default_template_tools_to_client(ctx, client)
    return client


def main(ctx: Dict):
    client = setup_model_client(ctx)

    logger.info(f"using instruction prompt:\n\n{client.load_model_template(ctx)}")

    with open(Path(ctx["llm"]["templates"]["initial_message"]), 'r') as fp:
        current_message = client.generate_preprocessed_template(ctx, fp.read())

    logger.info("starting prompting loop...")
    iteration = 1
    conclusion = None
    while True:
        logger.info("starting prompting iteration {}".format(iteration))

        responses = client.prompt_model(ctx, current_message)
        if len(responses) == 0:
            logger.warning("llm didn't do anything")
            with open(Path(ctx["llm"]["templates"]["stuck_message"]), 'r') as fp:
                current_message = client.generate_preprocessed_template(ctx, fp.read())
            continue

        messages = []
        errors = []
        for item_ctx, response in responses:
            item_ctx_str = f"{item_ctx.name}({item_ctx.arguments})"
            if response.error is not None:
                errors.append(f"{item_ctx_str}:\n\n{response.error.name}: {response.error.description}")
            if response.conclusion is not None:
                conclusion = response.conclusion
                break
            if response.response_message is not None:
                messages.append(f"{item_ctx_str}:\n\n{response.response_message}")
            if response.error is None and response.response_message is None:
                messages.append(f"{item_ctx_str}: No output")

        if conclusion is not None:
            break

        output_message = "Output:"

        if len(messages) > 0:
            output_message += "\n\n"
            output_message += "\n\n".join(messages)
        if len(errors) > 0:
            output_message += "\n\nErrors:\n\n"
            output_message += "\n\n".join(errors)
        if len(messages) == 0 and len(errors) == 0:
            output_message += " None"

        current_message = output_message

    print(f"Conclusion: the algorithm {'is' if conclusion.constant_time else 'is NOT'} constant-time")
    print(f"Reasoning: {conclusion.reasoning}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('config', nargs='*', type=Path, help='the config files to use')
    ap.add_argument('--default-config', type=Path, default=Path('./config/default.json'), help='the default configuration file to use')
    ap.add_argument("--dry-run", action="store_true", help='indicates to exit after generating the first prompts')
    args = ap.parse_args()

    cfg = load_configs(args.config, args.default_config)

    main(cfg)
    
