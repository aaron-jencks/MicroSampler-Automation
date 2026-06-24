from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

import pandas as pd
from qstate import StateContext
from tqdm import tqdm


class MicroSamplerCoreDeploymentState(Enum):
    LOOP_CHECK = "loop_check"
    PREPARE = "prepare"
    SIMULATION = "simulation"
    PARSE = "parse"
    STATS = "stats"
    KILL = "kill"


@dataclass
class MicroSamplerRunConfiguration:
    keys: List[str] = field(default_factory=list)
    suite: str = "bearssl"
    apps: List[str] = field(default_factory=list)
    phi: float = 0.9
    alpha: float = 0.1
    window: int = 1
    design: str = "baseline"
    iterations: int = 100


@dataclass
class MicroSamplerContext:
    run_config: MicroSamplerRunConfiguration = MicroSamplerRunConfiguration()
    current_app_index: int = 0
    current_key_index: int = 0
    log_prefix: Optional[Path] = None


@dataclass
class MicroSamplerLoopContext(StateContext):
    context: MicroSamplerContext
