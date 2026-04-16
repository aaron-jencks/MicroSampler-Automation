from abc import ABC, abstractmethod
from typing import Any, Dict


class ReportSection(ABC):
    def __init__(self, index: int, name: str):
        self.name = name
        self.index = index

    @abstractmethod
    def ingest_data(self, data: Any):
        pass

    @abstractmethod
    def body(self, ctx: Dict) -> str:
        pass

    @abstractmethod
    def reset(self):
        pass

    def generate_section(self, ctx: Dict) -> str:
        builder = f"##{self.name}\n\n"
        builder += self.body(ctx)
        return builder
