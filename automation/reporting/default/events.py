from typing import Any

from agents import Hypothesis, Implementation, Summarization
from reporting.events import ReportEvent
from simulation.struct import RunConfiguration
from states import LoopState
from stats import StatisticalAnalysisResults


class HypothesisEvent(ReportEvent):
    def __init__(self, iteration: int, payload: Hypothesis):
        super().__init__(iteration, LoopState.HYPOTHESIS, "output", payload)


class ImplementationEvent(ReportEvent):
    def __init__(self, iteration: int, payload: Implementation):
        super().__init__(iteration, LoopState.CODE_GEN, "output", payload)


class ImplementationErrorEvent(ReportEvent):
    def __init__(self, iteration: int, payload: Exception):
        super().__init__(iteration, LoopState.CODE_GEN, "build_error", payload)


class SimulationEvent(ReportEvent):
    def __init__(self, iteration: int, kind: str, payload: Any):
        super().__init__(iteration, LoopState.SIMULATION, kind, payload)


class SimulationDeploymentEvent(SimulationEvent):
    def __init__(self, iteration: int):
        super().__init__(iteration, "deployment", None)


class SimulationErrorEvent(SimulationEvent):
    def __init__(self, iteration: int, payload: Exception):
        super().__init__(iteration, "error", payload)


class AnalysisEvent(ReportEvent):
    def __init__(self, iteration: int, payload: StatisticalAnalysisResults):
        super().__init__(iteration, LoopState.ANALYSIS, "output", payload)


class SummarizationEvent(ReportEvent):
    def __init__(self, iteration: int, payload: Summarization):
        super().__init__(iteration, LoopState.SUMMARIZATION, "output", payload)


class ConclusionEvent(ReportEvent):
    def __init__(self, iteration: int, payload: StatisticalAnalysisResults):
        super().__init__(iteration, LoopState.CONCLUSION, "output", payload)
