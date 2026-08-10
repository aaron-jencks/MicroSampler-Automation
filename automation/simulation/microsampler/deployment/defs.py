from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional

import pandas as pd
from qstate import StateContext
from tqdm import tqdm


class MicroSamplerTCDeploymentState(StrEnum):
    HARNESS_VERIFY = "harness_verify"
    HARNESS_PREPARE = "harness_prepare"
    HARNESS_COMPILE = "harness_compile"
    LOOP_CHECK = "loop_check"
    MICROSAMPLER_DEPLOYMENT = "microsampler_deployment"
    DATA_COLLECTION = "data_collection"


@dataclass
class MicroSamplerTCRunConfiguration:
    keys: List[str] = field(default_factory=list)
    suite: str = "bearssl_synthetic"
    apps: List[str] = field(default_factory=list)
    phi: float = 0.9
    alpha: float = 0.1
    window: int = 1
    design: str = "baseline"
    iterations: int = 100


@dataclass
class MicroSamplerTCContext:
    run_config: MicroSamplerTCRunConfiguration = field(default_factory=MicroSamplerTCRunConfiguration)
    current_app_index: int = 0
    current_key_index: int = 0
    log_prefix: Optional[Path] = None


@dataclass
class MicroSamplerTCLoopContext(StateContext):
    context: MicroSamplerTCContext