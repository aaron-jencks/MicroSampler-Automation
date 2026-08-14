from .defs import PCFinderConfig
from tools import SubprocessError


class MicroSamplerPCParsingError(Exception):
    def __init__(self, cfg: PCFinderConfig):
        self.cfg = cfg
        super().__init__(f"parsing PCs failed for config: {cfg}")


class MicroSamplerSimulationError(SubprocessError):
    def __init__(self, code: int, stdout: str, stderr: str) -> None:
        super().__init__(code, stdout, stderr, f"simulation failed with code {code}")


class MicroSamplerParsingError(SubprocessError):
    def __init__(self, code: int, stdout: str, stderr: str) -> None:
        super().__init__(code, stdout, stderr, f"parsing failed with code {code}")


class MicroSamplerStatsError(SubprocessError):
    def __init__(self, code: int, stdout: str, stderr: str) -> None:
        super().__init__(code, stdout, stderr, f"stats failed with code {code}")
