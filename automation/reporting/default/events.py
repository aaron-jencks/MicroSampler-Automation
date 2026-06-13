from typing import Any

from agents.responses import Hypothesis, Implementation, Summarization
from agents.defs import LoopState
from reporting.events import ReportEvent, QSMReportEvent
from stats import StatisticalAnalysisResults


class ToolCallEvent(ReportEvent):
    def __init__(self, iteration: int, name: str):
        super().__init__(iteration, "tool", name)


class HypothesisEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: Hypothesis):
        super().__init__(iteration, LoopState.HYPOTHESIS, "output", payload)


class ImplementationEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: Implementation):
        super().__init__(iteration, LoopState.CODE_GEN, "output", payload)


class ImplementationErrorEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: Exception):
        super().__init__(iteration, LoopState.CODE_GEN, "build_error", payload)


class SimulationEvent(QSMReportEvent):
    def __init__(self, iteration: int, kind: str, payload: Any):
        super().__init__(iteration, LoopState.SIMULATION, kind, payload)


class SimulationDeploymentEvent(SimulationEvent):
    def __init__(self, iteration: int):
        super().__init__(iteration, "deployment", None)


class SimulationErrorEvent(SimulationEvent):
    def __init__(self, iteration: int, payload: Exception):
        super().__init__(iteration, "error", payload)


class AnalysisEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: StatisticalAnalysisResults):
        super().__init__(iteration, LoopState.ANALYSIS, "output", payload)


class SummarizationEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: Summarization):
        super().__init__(iteration, LoopState.SUMMARIZATION, "output", payload)


class ConclusionEvent(QSMReportEvent):
    def __init__(self, iteration: int, payload: StatisticalAnalysisResults):
        super().__init__(iteration, LoopState.CONCLUSION, "output", payload)
