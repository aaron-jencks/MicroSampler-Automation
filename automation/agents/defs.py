from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd
from qstate import StateContext

from stats import StatisticalAnalysisResults
from .responses import Hypothesis, Implementation, Summarization


class LoopState(Enum):
    HYPOTHESIS = "hypothesis"
    CODE_GEN = "implementation"
    SIMULATION = "simulation"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    CONCLUSION = "conclusion"


@dataclass
class GovernorContext:
    iteration: int = 1
    current_summarization: Optional[Summarization] = None
    current_hypothesis: Optional[Hypothesis] = None
    current_implementation: Optional[Implementation] = None
    current_stats: Optional[StatisticalAnalysisResults] = None
    current_results: Optional[pd.DataFrame] = None
    simulation_feedback: Optional[str] = None


class AgentLoopContext(StateContext):
    context: GovernorContext
