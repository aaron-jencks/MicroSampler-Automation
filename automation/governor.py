import argparse
from dataclasses import dataclass
import datetime as dt
from enum import Enum
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

import pandas as pd
from cascade_config import CascadeConfig
from pydantic import BaseModel

from agents import Hypothesis, Implementation, Summarization
# from reporting.default import create_default_report_sections
# from reporting.logger import ReportLog
from prompting.client import Agent
from prompting.templates import TemplateController
from simulation.api.ccopy import CCopyDeploymentController
from simulation.exceptions import IllegalCodeError, BuildError, SimulationTimeoutError, SimulationFailureError
from states import LoopState
from stats import StatisticalAnalysisResults, generate_statistical_analysis
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


@dataclass
class LoopContext:
    iteration: int = 1
    loop_state: LoopState = LoopState.HYPOTHESIS
    current_summarization: Optional[Summarization] = None
    current_hypothesis: Optional[Hypothesis] = None
    current_implementation: Optional[Implementation] = None
    current_stats: Optional[StatisticalAnalysisResults] = None
    current_results: Optional[pd.DataFrame] = None
    simulation_feedback: Optional[str] = None


def main(ctx: Dict, dry: bool = False):
    # reporter = ReportLog()
    # create_default_report_sections(ctx, reporter)

    template_controller = TemplateController()
    add_default_template_tools_to_client(ctx, template_controller)

    deployment_controller = CCopyDeploymentController(ctx)

    agents = {
        LoopState.HYPOTHESIS: create_agent_from_config(ctx, template_controller, "hypothesis", Hypothesis, dry),
        LoopState.CODE_GEN: create_agent_from_config(ctx, template_controller, "implementation", Implementation, dry),
        LoopState.SUMMARIZATION: create_agent_from_config(ctx, template_controller, "summarization", Summarization, dry),
    }

    logger.info("starting prompting loop...")
    current_state = LoopContext()
    # conclusion = None
    while True:
        if current_state.loop_state == LoopState.HYPOTHESIS:
            logger.info("starting hypothesis forming for iteration {}".format(current_state.iteration))
            agent = agents[current_state.loop_state]
            prompt = template_controller.process_template(
                ctx,
                agent.get_agent_prompt("input"),
                {
                    "summary": current_state.current_summarization if current_state.current_summarization is not None else None,
                }
            )
            current_state.current_hypothesis = agent.prompt_model(ctx, prompt)
            current_state.loop_state = LoopState.CODE_GEN
        elif current_state.loop_state == LoopState.CODE_GEN:
            logger.info("starting attack generation for iteration {}".format(current_state.iteration))
            agent = agents[current_state.loop_state]
            prompt = template_controller.process_template(
                ctx,
                agent.get_agent_prompt("input"),
                {
                    "current_hypothesis": current_state.current_hypothesis,
                    "feedback": current_state.simulation_feedback
                }
            )
            current_state.current_implementation = agent.prompt_model(ctx, prompt)
            current_state.loop_state = LoopState.SIMULATION
        elif current_state.loop_state == LoopState.SIMULATION:
            logger.info("starting simulation for iteration {}".format(current_state.iteration))
            current_state.current_results = None
            current_state.current_stats = None
            current_state.simulation_feedback = None
            try:
                current_state.current_results = deployment_controller.deploy_test_case(
                    current_state.current_implementation.attack_code,
                    config=current_state.current_hypothesis.run_configuration
                )
                current_state.loop_state = LoopState.ANALYSIS
            except (IllegalCodeError, BuildError) as e:
                logger.info("code was illegal or did not build successfully")
                current_state.simulation_feedback = str(e)
                current_state.loop_state = LoopState.CODE_GEN
            except (SimulationTimeoutError, SimulationFailureError) as e:
                logger.info("simulation timed out or failed")
                current_state.simulation_feedback = str(e)
                current_state.loop_state = LoopState.SUMMARIZATION
        elif current_state.loop_state == LoopState.ANALYSIS:
            logger.info("starting analysis for iteration {}".format(current_state.iteration))
            current_state.current_stats = generate_statistical_analysis(current_state.current_results)
            # TODO early stopping happens here
            if current_state.current_stats.iteration_score > 0.95:
                logger.info(f"analysis hit threshold with a score of {current_state.current_stats.iteration_score:0.4f}")
                current_state.loop_state = LoopState.CONCLUSION
                continue
            current_state.loop_state = LoopState.SUMMARIZATION
        elif current_state.loop_state == LoopState.SUMMARIZATION:
            logger.info("starting summarization for iteration {}".format(current_state.iteration))
            agent = agents[current_state.loop_state]
            prompt = template_controller.process_template(
                ctx,
                agent.get_agent_prompt("input"),
                # TODO define analysis results
                {
                    "current_hypothesis": current_state.current_hypothesis,
                    "stats": current_state.current_stats,  # should probably also include hypothesis as well.
                    "feedback": current_state.simulation_feedback,
                    "implementation": current_state.current_implementation.attack_code,
                }
            )
            current_state.current_summarization = agent.prompt_model(ctx, prompt)
            current_state.simulation_feedback = None
            current_state.loop_state = LoopState.HYPOTHESIS
            current_state.iteration += 1
        elif current_state.loop_state == LoopState.CONCLUSION:
            logger.info("exiting loop")
            break

    # logger.info(f"Conclusion: the algorithm {'is' if conclusion.constant_time else 'is NOT'} constant-time")
    # logger.info(f"Reasoning: {conclusion.reasoning}")
    # reporter.generate_report(ctx)


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
    
