from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RunConfiguration:
    global_iterations: int
    inner_iterations: int
    run_name: str
    random_seed: int


@dataclass
class RunResult:
    stdout: Optional[str]
    stderr: Optional[str]
    output_files: Optional[List[str]]
    errored: bool
    timedout: bool
    return_code: int


@dataclass
class BuildResult:
    stdout: str
    stderr: str
    return_code: int