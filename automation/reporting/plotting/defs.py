from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

from pandas import DataFrame


class PlotGenerator(ABC):
    def __init__(self, fname: Path):
        self.fname = fname

    @abstractmethod
    def generate_plot(self, ctx: Dict, data: DataFrame):
        pass
