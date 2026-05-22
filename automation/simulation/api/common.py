from abc import ABC, abstractmethod

import pandas as pd


class DeploymentController(ABC):
    @abstractmethod
    def deploy_test_case(self, code: str, **kwargs) -> pd.DataFrame:
        pass
