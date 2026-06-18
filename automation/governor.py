import argparse
import datetime as dt
import logging
from pathlib import Path
from typing import Dict, List, Type

from cascade_config import CascadeConfig
from pydantic import BaseModel
from qstate import QSM

from agents.responses import Hypothesis, Implementation, Summarization
from agents.defs import GovernorContext
from config import BaseConfig, parse_args
from reporting.default.sections import create_default_report_sections
from reporting.logger import ReportLog
from prompting.client import Agent
from prompting.templates import TemplateController
from prompting.tools import AgentToolRegistry
from simulation.api.ccopy import CCopyDeploymentController
from templates import add_default_template_tools_to_client
from tools import create_default_agent_tool_registry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_logging(ctx: BaseConfig):
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    )

    log_path = Path(ctx.logging.prefix) / ctx.logging.output
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


def create_agent_from_config(
        ctx: BaseConfig, template_controller: TemplateController,
        name: str, output_format: Type[BaseModel],
        tool_registry: AgentToolRegistry,
        dry: bool = False
) -> Agent:
    agent_definition = ctx.agents[name]
    system_prompt_path = agent_definition.templates["system"]
    with open(system_prompt_path, 'r') as fp:
        system_prompt = template_controller.process_template(ctx, fp.read())
    tools = tool_registry.create_tools(agent_definition.tools)
    return Agent(
        ctx, agent_definition.model,
        name, output_format,
        system_prompt, agent_definition.templates,
        tools,
        dry
    )


def main(ctx: BaseConfig, dry: bool = False):
    reporter = ReportLog()
    for section in create_default_report_sections():
        reporter.add_section(section)

    template_controller = TemplateController()
    add_default_template_tools_to_client(ctx, template_controller)

    state = GovernorContext()

    deployment_controller = QSM.from_config_file(
        ctx.deployment_qsm_path,
        ctx=ctx,
    )
    tool_registry = create_default_agent_tool_registry(ctx, state, reporter)

    q = QSM.from_config_file(
        ctx.governor_qsm_path,
        ctx=ctx,
        reporter=reporter,
        template_controller=template_controller,
        deployment_controller=deployment_controller,
        hypothesis_agent=create_agent_from_config(ctx, template_controller, "hypothesis", Hypothesis, tool_registry, dry),
        implementation_agent=create_agent_from_config(ctx, template_controller, "implementation", Implementation, tool_registry, dry),
        summarization_agent=create_agent_from_config(ctx, template_controller, "summarization", Summarization, tool_registry, dry),
    )
    q.context = state

    logger.info("starting prompting loop...")
    q.loop()

    reporter.generate_report(ctx)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help='indicates to exit after generating the first prompts')
    ap.add_argument('--run-name', type=str, default=None, help='the name of the run to use, overrides the one in the config file')
    args, cfg = parse_args(ap)

    if args.run_name is not None:
        cfg.final_report.run_name = args.run_name

    setup_logging(cfg)
    main(cfg, args.dry_run)
    
