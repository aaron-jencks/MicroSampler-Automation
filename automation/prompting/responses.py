from abc import ABC, abstractmethod

from pydantic import BaseModel


class DryRunnableBaseModel(BaseModel, ABC):
    @classmethod
    @abstractmethod
    def from_dry_run(cls):
        pass