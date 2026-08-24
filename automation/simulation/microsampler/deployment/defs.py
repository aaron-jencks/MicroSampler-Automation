from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Optional
import uuid

import pandas as pd
from qstate import StateContext
from tqdm import tqdm

from ..core.defs import MicroSamplerRunConfiguration, MicroSamplerContext
from .struct import BuildResult


class MicroSamplerTCDeploymentState(StrEnum):
    PREPARE = "prepare"
    HARNESS_VERIFY = "harness_verify"
    HARNESS_PREPARE = "harness_prepare"
    HARNESS_COMPILE = "harness_compile"
    KEY_PREPARE = "key_prepare"
    DEPLOYMENT_PREPARE = "deployment_prepare"
    LOOP_CHECK = "loop_check"
    MICROSAMPLER_DEPLOYMENT = "microsampler_deployment"
    DATA_COLLECTION = "data_collection"


@dataclass
class MicroSamplerTCRunConfiguration(MicroSamplerRunConfiguration):
    run_name: str = field(default_factory=lambda: uuid.uuid4().hex)
    global_iterations: int = 100
    key_size: int = 256


@dataclass
class MicroSamplerTCContext(MicroSamplerContext):
    run_config: MicroSamplerTCRunConfiguration = field(default_factory=MicroSamplerTCRunConfiguration)
    implementation: Optional[str] = None
    build_status: Optional[BuildResult] = None
    current_global_iteration: int = 0
    current_key_name: Optional[str] = None


@dataclass
class MicroSamplerTCLoopContext(StateContext):
    context: MicroSamplerTCContext