from typing import Dict

import pandas as pd

from simulation.api.common import DeploymentController
from simulation.struct import RunConfiguration
from simulation.utils import write_attack_source, run_simulation


class CCopyDeploymentController(DeploymentController):
    def __init__(self, ctx: Dict):
        self.ctx = ctx

    def deploy_test_case(self, code: str, **kwargs) -> pd.DataFrame:
        if "config" not in kwargs or not isinstance(kwargs["config"], RunConfiguration):
            raise ValueError("need a run configuration for deployment")
        write_attack_source(self.ctx, code)
        return run_simulation(self.ctx, kwargs["config"])
