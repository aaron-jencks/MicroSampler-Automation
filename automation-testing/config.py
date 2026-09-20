from argparse import ArgumentParser, Namespace
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from cascade_config import CascadeConfig
from pydantic import BaseModel


class AutomationSettings(BaseModel):
    name: Optional[str] = None
    configs: List[Path]
    executable: Path = Path("governor.py")
    cwd: Path = Path("../automation")


class BaseConfig(BaseModel):
    baseline: AutomationSettings
    candidates: List[AutomationSettings]
    candidate_iterations: int = 10
    performance_log_directory: Path = Path("./performance_logs")


def parse_configs(configs: List[Path]) -> BaseConfig:
    parser = CascadeConfig(validation_schema=BaseConfig.model_json_schema())
    for config in configs:
        parser.add_json(str(config.resolve().absolute()))
    data = parser.parse()
    return BaseConfig.model_validate(data)


def parse_args(ap: ArgumentParser) -> Tuple[Namespace, BaseConfig]:
    ap.add_argument("configs", type=Path, nargs="*", default=[], help="The config files to use")
    ap.add_argument("-v", "--verbose", action="store_true", help="Enables debug logging")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    return args, parse_configs(args.configs)
