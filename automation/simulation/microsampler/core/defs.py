from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from simulation.microsampler.pc_finder import UUTPCAddresses


class MicroSamplerCoreDeploymentState(StrEnum):
    LOOP_CHECK = "loop_check"
    PREPARE = "prepare"
    FIND_PCS = "find_pcs"
    SIMULATION = "simulation"
    PARSE = "parse"
    STATS = "stats"


@dataclass
class PCFinderConfig:
    obj_file: Path
    roi_function: str
    uut_function: str
    warmup: bool = False


@dataclass
class MicroSamplerRunConfiguration:
    keys: List[str] = field(default_factory=list)
    suite: str = "bearssl_synthetic"
    apps: List[str] = field(default_factory=list)
    phi: float = 0.9
    alpha: float = 0.1
    window: int = 1
    design: str = "baseline"
    iterations: int = 100
    pc_config: PCFinderConfig = field(default_factory=PCFinderConfig)


@dataclass
class MicroSamplerContext:
    run_config: MicroSamplerRunConfiguration = field(default_factory=MicroSamplerRunConfiguration)
    current_app_index: int = 0
    current_key_index: int = 0
    log_prefix: Optional[Path] = None
    pc_addresses: Optional[UUTPCAddresses] = None


@dataclass
class MicroSamplerLoopContext(StateContext):
    context: MicroSamplerContext
