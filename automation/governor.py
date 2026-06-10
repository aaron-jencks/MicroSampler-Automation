import argparse
import datetime as dt
import logging
from pathlib import Path
from typing import Dict, List, Type

from cascade_config import CascadeConfig
from pydantic import BaseModel
from qsm import QSM

from agents.responses import Hypothesis, Implementation, Summarization
from agents.defs import LoopState, GovernorContext
from agents.states import HypothesisState, ImplementationState, SimulationState, AnalysisState, SummarizationState, \
    ConclusionState
from reporting.default.sections import create_default_report_sections
from reporting.logger import ReportLog
from prompting.client import Agent
from prompting.templates import TemplateController
from simulation.api.ccopy import CCopyDeploymentController
from templates import add_default_template_tools_to_client


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_logging(ctx: Dict):
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    )

    log_path = Path(ctx["logging"]["prefix"]) / ctx["logging"]["output"]
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
        ctx: Dict, template_controller: TemplateController,
        name: str, output_format: Type[BaseModel],
        dry: bool = False
) -> Agent:
    agent_definition = ctx["agents"][name]
    system_prompt_path = agent_definition["templates"]["system"]
    with open(system_prompt_path, 'r') as fp:
        system_prompt = template_controller.process_template(ctx, fp.read())
    return Agent(
        ctx, agent_definition["model"],
        name, output_format,
        system_prompt, agent_definition["templates"],
        dry
    )


def main(ctx: Dict, dry: bool = False):
    reporter = ReportLog()
    for section in create_default_report_sections():
        reporter.add_section(section)

    template_controller = TemplateController()
    add_default_template_tools_to_client(ctx, template_controller)

    deployment_controller = CCopyDeploymentController(ctx)

    q_context = GovernorContext()
    q = QSM(
        initial_state=LoopState.HYPOTHESIS.value,
        initial_context=q_context,
    )
    q.state_map[LoopState.HYPOTHESIS.value] = HypothesisState(
        ctx,
        create_agent_from_config(ctx, template_controller, "hypothesis", Hypothesis, dry),
        reporter, template_controller
    )
    q.state_map[LoopState.CODE_GEN.value] = ImplementationState(
        ctx,
        create_agent_from_config(ctx, template_controller, "implementation", Implementation, dry),
        reporter, template_controller
    )
    q.state_map[LoopState.SIMULATION.value] = SimulationState(ctx, reporter, deployment_controller)
    q.state_map[LoopState.ANALYSIS.value] = AnalysisState(ctx, reporter)
    q.state_map[LoopState.SUMMARIZATION.value] = SummarizationState(
        ctx,
        create_agent_from_config(ctx, template_controller, "summarization", Summarization, dry),
        reporter, template_controller
    )
    q.state_map[LoopState.CONCLUSION.value] = ConclusionState(ctx, reporter)

    logger.info("starting prompting loop...")
    q.loop()

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
    
