from abc import ABC
import logging

from qstate import State, StateContext, QSM

from agents.defs import LoopState, AgentLoopContext
from config import BaseConfig
from prompting.client import Agent
from prompting.templates import TemplateController
from reporting.default.events import HypothesisEvent, ImplementationEvent, SimulationDeploymentEvent, \
    ImplementationErrorEvent, SimulationErrorEvent, AnalysisEvent, SummarizationEvent, ConclusionEvent
from reporting.logger import ReportLog
from simulation.ccopy.exceptions import IllegalCodeError, BuildError, SimulationTimeoutError, SimulationFailureError
from stats import generate_statistical_analysis

logger = logging.getLogger(__name__)


class GovernorLoopState(State, ABC):
    def __init__(self, ctx: BaseConfig, reporter: ReportLog):
        super().__init__()
        self.config = ctx
        self.reporter = reporter

    @staticmethod
    def append_loop_state(ctx: StateContext, loop_state: LoopState):
        ctx.queue.append(loop_state.value)


class AgentLoopState(GovernorLoopState, ABC):
    def __init__(self, ctx: BaseConfig, agent: Agent, reporter: ReportLog, template_controller: TemplateController):
        super().__init__(ctx, reporter)
        self.agent = agent
        self.template_controller = template_controller

    def prompt_model(self, template: str, **kwargs):
        prompt = self.template_controller.process_template(
            self.config,
            self.agent.get_agent_prompt(template),
            kwargs
        )
        return self.agent.prompt_model(self.config, prompt)


class HypothesisState(AgentLoopState):
    def execute(self, ctx: AgentLoopContext):
        logger.info("starting hypothesis forming for iteration {}".format(ctx.context.iteration))
        ctx.context.current_hypothesis = self.prompt_model(
            "input",
            summary=ctx.context.current_summarization if ctx.context.current_summarization is not None else None,
        )
        self.reporter.log(HypothesisEvent(ctx.context.iteration, ctx.context.current_hypothesis))
        self.append_loop_state(ctx, LoopState.CODE_GEN)


class ImplementationState(AgentLoopState):
    def execute(self, ctx: AgentLoopContext):
        logger.info("starting attack generation for iteration {}".format(ctx.context.iteration))
        ctx.context.current_implementation = self.prompt_model(
            "input",
            current_hypothesis=ctx.context.current_hypothesis,
            feedback=ctx.context.simulation_feedback,
        )
        self.reporter.log(ImplementationEvent(ctx.context.iteration, ctx.context.current_implementation))
        self.append_loop_state(ctx, LoopState.SIMULATION)


class SimulationState(GovernorLoopState):
    def __init__(self, ctx: BaseConfig, reporter: ReportLog, deployment_controller: QSM):
        super().__init__(ctx, reporter)
        self.deployment_controller = deployment_controller

    def execute(self, ctx: AgentLoopContext):
        logger.info("starting simulation for iteration {}".format(ctx.context.iteration))
        ctx.context.current_results = None
        ctx.context.current_stats = None
        ctx.context.simulation_feedback = None
        self.deployment_controller.context.implementation = ctx.context.current_implementation.attack_code
        self.deployment_controller.context.configuration = ctx.context.current_hypothesis.run_configuration
        sim_err = self.deployment_controller.loop()
        self.reporter.log(SimulationDeploymentEvent(ctx.context.iteration))
        if sim_err is not None:
            ctx.context.simulation_feedback = str(sim_err)
            if isinstance(sim_err, IllegalCodeError) or isinstance(sim_err, BuildError):
                logger.info("code was illegal or did not build successfully")
                self.reporter.log(ImplementationErrorEvent(ctx.context.iteration, sim_err))
                self.append_loop_state(ctx, LoopState.CODE_GEN)
                return
            elif isinstance(sim_err, SimulationTimeoutError) or isinstance(sim_err, SimulationFailureError):
                logger.info("simulation timed out or failed")
                self.reporter.log(SimulationErrorEvent(ctx.context.iteration, sim_err))
                self.append_loop_state(ctx, LoopState.SUMMARIZATION)
                return
            else:
                raise ValueError(f"Unknown response from deployment controller: {sim_err}")
        ctx.context.current_results = self.deployment_controller.context.final_table
        self.append_loop_state(ctx, LoopState.ANALYSIS)


class AnalysisState(GovernorLoopState):
    def execute(self, ctx: AgentLoopContext):
        logger.info("starting analysis for iteration {}".format(ctx.context.iteration))
        ctx.context.current_stats = generate_statistical_analysis(ctx.context.current_results)
        self.reporter.log(AnalysisEvent(ctx.context.iteration, ctx.context.current_stats))
        # TODO early stopping happens here
        # TODO split this early stopping checking into its own state
        logger.info(f"Current average score: {ctx.context.current_stats.iteration_score:0.4f}")
        if ctx.context.current_stats.iteration_score > 0.95:
            logger.info(f"analysis hit score threshold")
            self.append_loop_state(ctx, LoopState.CONCLUSION)
            return
        self.append_loop_state(ctx, LoopState.SUMMARIZATION)


class SummarizationState(AgentLoopState):
    def execute(self, ctx: AgentLoopContext):
        logger.info("starting summarization for iteration {}".format(ctx.context.iteration))
        ctx.context.current_summarization = self.prompt_model(
            "input",
            current_hypothesis=ctx.context.current_hypothesis,
            feedback=ctx.context.simulation_feedback,
            stats=ctx.context.current_stats,
            implementation=ctx.context.current_implementation.attack_code,
        )
        self.reporter.log(SummarizationEvent(ctx.context.iteration, ctx.context.current_summarization))
        ctx.context.simulation_feedback = None
        ctx.context.iteration += 1
        self.append_loop_state(ctx, LoopState.HYPOTHESIS)


class ConclusionState(GovernorLoopState):
    def execute(self, ctx: AgentLoopContext):
        logger.info("exiting loop")
        self.reporter.log(ConclusionEvent(ctx.context.iteration, ctx.context.current_stats))
