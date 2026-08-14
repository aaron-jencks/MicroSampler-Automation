from dataclasses import dataclass


@dataclass
class BuildResult:
    stdout: str
    stderr: str
    return_code: int
