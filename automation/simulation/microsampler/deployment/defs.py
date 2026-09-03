from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional
import uuid

from qstate import StateContext

from ..core.defs import MicroSamplerRunConfiguration, MicroSamplerContext
from .struct import BuildResult


class MicroSamplerTCDeploymentState(StrEnum):
    INITIAL = "initial_state"
    PREPARE = "prepare"
    HARNESS_VERIFY = "harness_verify"
    HARNESS_PREPARE = "harness_prepare"
    HARNESS_COMPILE = "harness_compile"
    KEY_PREPARE = "key_prepare"
    DEPLOYMENT_PREPARE = "deployment_prepare"
    LOOP_CHECK = "loop_check"
    MICROSAMPLER_DEPLOYMENT = "microsampler_deployment"
    MICROSAMPLER_SIMULATION = "microsampler_simulation"
    MICROSAMPLER_PARSE = "microsampler_parse"
    MICROSAMPLER_STATS = "microsampler_stats"
    DATA_COLLECTION = "data_collection"


@dataclass
class MicroSamplerTCRunConfiguration(MicroSamplerRunConfiguration):
    run_name: str = field(default_factory=lambda: uuid.uuid4().hex)
    global_iterations: int = 100

    # Number of hexadecimal characters written to each key file.
    # Existing MicroSampler keys contain 256 hexadecimal characters.
    key_size: int = 256

    # Tests can provide a fixed value. Production runs leave this as None.
    fixed_key: Optional[str] = None


@dataclass
class MicroSamplerTCIterationResult:
    global_iteration: int
    key_name: str
    key_file: Path
    executable: Path
    log_prefix: Path
    simulation_trace: Path
    parsed_state: Path
    sets_file: Path
    stats_output: Path
    simulation_log: Path
    parse_log: Path
    stats_log: Path


@dataclass
class MicroSamplerTCContext(MicroSamplerContext):
    run_config: MicroSamplerTCRunConfiguration = field(
        default_factory=MicroSamplerTCRunConfiguration
    )
    implementation: Optional[str] = None
    build_status: Optional[BuildResult] = None
    current_global_iteration: int = 0
    current_key_name: Optional[str] = None
    current_key_file: Optional[Path] = None
    collected_data: List[MicroSamplerTCIterationResult] = field(
        default_factory=list
    )


@dataclass
class MicroSamplerTCLoopContext(StateContext):
    context: MicroSamplerTCContext
