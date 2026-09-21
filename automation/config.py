from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cascade_config import CascadeConfig
from pydantic import BaseModel


class UUTConfig(BaseModel):
    prefix: Path = Path("bearssl-0.6/ccopy/v2/uut/")
    file: str = "uut.c"
    description_file: str = "uut_description.md"


class HarnessConfig(BaseModel):
    prefix: Path = Path("./harness/")
    executable: str = "harness"
    target: str = "attack.c"
    assembly_file: str = "attack.s"
    deployment_prefix: Path = Path("bearssl-0.6/ccopy/v2/deploy/")
    timeout: int = 60
    allowed_references: List[str] = [
        "encryption_util.h",
        "error.h",
        "context.h"
    ]
    make_defines: List[str] = ["LOCAL=1"]
    uut: UUTConfig = UUTConfig()


class PCFinderConfig(BaseModel):
    obj_file: Optional[Path] = None         # If none, derives from the harness output files
    roi_function: str = "test_ccopy_loop"
    uut_function: str = "ccopy"
    warmup: bool = True


class MicroSamplerConfig(BaseModel):
    working_directory: Path = Path("..")
    scripts_prefix: Path = Path("../scripts/")
    deployment_prefix: Path = Path("..")
    riscv_root: Path = Path("/local/scratch/riscv")
    core_deployment_qsm: Path = Path("config/governor/microsampler_deployment_core_qsm.json")
    pc_finder: PCFinderConfig = PCFinderConfig()
    suite: str = "microbench"
    app: str = "ct_ccopy"


class InterpreterConfig(BaseModel):
    venv_path: Path = Path("bearssl-0.6/ccopy/v2/interpreter/venv/")
    requirements_path: Path = Path("config/definitions/requirements.txt")
    timeout: int = 60


class LLMCompactionConfig(BaseModel):
    enabled: bool = True
    trigger_tokens: int = 300000
    keep_messages: int = 12
    trim_tokens_to_summarize: int = 4000


class LLMConfig(BaseModel):
    api_key: Optional[str] = None
    context_compaction: LLMCompactionConfig = LLMCompactionConfig()


class AgentConfig(BaseModel):
    model: str = "gpt-5.6-luna"
    templates: Dict[str, Path]
    tools: List[str] = []
    reasoning_effort: Optional[str] = None


class LogConfig(BaseModel):
    prefix: Path = Path("bearssl-0.6/ccopy/v2/logs/")
    output: str = "v2_output.log"


class FinalReportConfig(BaseModel):
    prefix: Path = Path("bearssl-0.6/ccopy/v2/final_report")
    run_name: str = "ccopy_v2"
    file: str = "final_report.html"
    plots_prefix: str = "images"
    clear_report_area: bool = True


class InitialAttackConfig(BaseModel):
    hypothesis: str = "Initial run with a stub implementation for a sanity check to verify that the code is constant time without modification."
    file: Path = Path("bearssl-0.6/ccopy/v2/initial_attack.c")
    global_iterations: int = 10
    inner_iterations: int = 100


class BaseConfig(BaseModel):
    microsampler: MicroSamplerConfig = MicroSamplerConfig()
    harness: HarnessConfig = HarnessConfig()
    interpreter: InterpreterConfig = InterpreterConfig()
    llm: LLMConfig = LLMConfig()
    deployment_qsm_path: Path = Path("config/governor/ccopy_deployment_qsm.json")
    governor_qsm_path: Path = Path("config/governor/ccopy_qsm.json")
    max_loop_iterations: int = 10
    agents: Dict[str, AgentConfig] = {
        "hypothesis": AgentConfig(
            templates={
                "system": Path("bearssl-0.6/ccopy/v2/prompts/hypothesis/system-prompt.txt"),
                "input": Path("bearssl-0.6/ccopy/v2/prompts/hypothesis/feedback-prompt.txt"),
            }
        ),
        "implementation": AgentConfig(
            templates={
                "system": Path("bearssl-0.6/ccopy/v2/prompts/implementation/system-prompt.txt"),
                "input": Path("bearssl-0.6/ccopy/v2/prompts/implementation/feedback-prompt.txt"),
            },
        ),
        "summarization": AgentConfig(
            templates={
                "system": Path("bearssl-0.6/ccopy/v2/prompts/summarization/system-prompt.txt"),
                "input": Path("bearssl-0.6/ccopy/v2/prompts/summarization/feedback-prompt.txt"),
            },
            tools=["read_attack_assembly"]
        ),
    }
    initial_attack: InitialAttackConfig = InitialAttackConfig()
    logging: LogConfig = LogConfig()
    final_report: FinalReportConfig = FinalReportConfig()


def parse_configs(configs: List[Path]) -> BaseConfig:
    parser = CascadeConfig(validation_schema=BaseConfig.model_json_schema())
    for config in configs:
        parser.add_json(str(config.resolve().absolute()))
    data = parser.parse()
    return BaseConfig.model_validate(data)


def parse_args(ap: ArgumentParser) -> Tuple[Namespace, BaseConfig]:
    ap.add_argument("--configs", type=Path, nargs="*", default=[], help="The config files to use")
    args = ap.parse_args()
    return args, parse_configs(args.configs)
