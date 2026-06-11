from abc import ABC, abstractmethod
from typing import List

import markdown

from config import BaseConfig
from reporting.events import ReportEvent


class ReportSection(ABC):
    def __init__(self, index: int, name: str):
        self.name = name
        self.index = index

    @abstractmethod
    def body(self, ctx: BaseConfig, events: List[ReportEvent]) -> str:
        pass

    def generate_section(self, ctx: BaseConfig, events: List[ReportEvent]) -> str:
        builder = f"<details>\n<summary>{self.name}</summary>\n\n"
        builder += markdown.markdown(self.body(ctx, events), extensions=['tables', 'fenced_code'])
        builder += "\n\n</details>"
        return builder
