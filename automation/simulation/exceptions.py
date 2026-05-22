from simulation.struct import RunResult, BuildResult


class IllegalCodeError(Exception):
    def __init__(self, src: str):
        self.source = src
        super().__init__(f"illegal code: the attack code you wrote does not pass preliminary validation, \
        you may have unallowed local references.")


class BuildError(Exception):
    def __init__(self, res: BuildResult):
        self.result = res
        super().__init__(f"build failed with code: {res.return_code}")


class SimulationTimeoutError(Exception):
    def __init__(self, res: RunResult, limit_seconds: float):
        self.result = res
        self.limit = limit_seconds
        super().__init__(f"simulation timed out, run exceeded {limit_seconds} seconds")


class SimulationFailureError(Exception):
    def __init__(self, res: RunResult):
        self.result = res
        super().__init__(f"simulation failed with code: {res.return_code}")