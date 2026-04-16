from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from reporting.sections import ReportSection
from reporting.utils import get_report_directory
from workbench import get_workbench_path


logger = logging.getLogger(__name__)


class ReportDataType(Enum):
    TRANSCRIPT = 1
    SUGGESTION = 2
    SIMULATION = 3
    LLM_REPORT = 4


class ReportLog:
    def __init__(self):
        self.simulation_count = 0
        self.sections: Dict[ReportDataType, List[ReportSection]] = {}

    def add_section(self, dt: ReportDataType, section: ReportSection):
        if dt not in self.sections:
            self.sections[dt] = []
        self.sections[dt].append(section)

    def _log_data(self, t: ReportDataType, d: Any):
        if t not in self.sections:
            return
        for s in self.sections[t]:
            s.ingest_data(d)

    def log_transcript(self, line: Optional[str]):
        if line is None:
            return
        self._log_data(ReportDataType.TRANSCRIPT, line)

    def log_suggestion(self, suggestion: str):
        self._log_data(ReportDataType.SUGGESTION, suggestion)

    def log_simulation(self, run_name: str):
        self.simulation_count += 1
        self._log_data(ReportDataType.SIMULATION, run_name)

    def clear_simulations(self):
        self.simulation_count = 0
        if ReportDataType.SIMULATION not in self.sections:
            return
        for s in self.sections[ReportDataType.SIMULATION]:
            s.reset()

    def read_llm_report(self, ctx: Dict) -> str:
        fpath = get_workbench_path(ctx) / ctx['llm']['report_name']
        if not fpath.exists():
            return "LLM did not output a report"
        with open(fpath, 'r') as fp:
            return fp.read()

    def generate_report(self, ctx: Dict):
        logger.info(f'generating report to {ctx["final_report"]["file"]}')
        fpath = get_report_directory(ctx) / ctx["final_report"]["file"]
        builder = f"# {ctx['final_report']['run_name']} Final Report\n\n"

        sections = []
        for sl in list(self.sections.values()):
            sections.extend(sl)
        sections.sort(key=lambda s: s.index)

        builder += "\n\n".join([s.generate_section(ctx) for s in sections])

        with open(fpath, 'w+') as fp:
            fp.write(builder)
