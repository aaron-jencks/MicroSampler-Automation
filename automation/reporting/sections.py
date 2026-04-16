from abc import ABC, abstractmethod
from typing import Any, Dict

import markdown


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
        builder = f"<details>\n<summary>{self.name}</summary>\n\n"
        builder += markdown.markdown(self.body(ctx), extensions=['tables', 'fenced_code'])
        builder += "\n\n</details>"
        return builder
