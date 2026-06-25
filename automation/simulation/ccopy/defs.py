from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Optional

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from .struct import RunConfiguration, BuildResult, RunResult


class CCopyDeploymentState(StrEnum):
    VERIFY = "verify"
    WRITE = "write"
    COMPILE = "compile"
    PREPARE = "prepare"
    RUN_FULL = "run_full"
    RUN_LOOP = "run_loop"
    TABULATE = "tabulate"


@dataclass
class CCopyDeploymentContext:
    implementation: Optional[str] = None
    configuration: Optional[RunConfiguration] = None
    build_status: Optional[BuildResult] = None
    results: List[RunResult] = field(default_factory=list)
    current_global_iteration: int = 0
    pbar: Optional[tqdm] = None
    final_table: Optional[pd.DataFrame] = None


@dataclass
class CCopyLoopContext(StateContext):
    context: CCopyDeploymentContext
