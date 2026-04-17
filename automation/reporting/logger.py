from enum import Enum
import logging
import shutil
from typing import Any, Dict, List, Optional

import markdown

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

        prefix = get_report_directory(ctx)
        if ctx["final_report"]["clear_report_area"] and prefix.exists():
            shutil.rmtree(prefix)
            prefix.mkdir(parents=True, exist_ok=True)
        plots_prefix = prefix / ctx["final_report"]["plots_prefix"]
        plots_prefix.mkdir(parents=True, exist_ok=True)

        builder = f"<h1>{ctx['final_report']['run_name']} Final Report</h1>\n\n"

        sections = []
        for sl in list(self.sections.values()):
            sections.extend(sl)
        sections.sort(key=lambda s: s.index)

        builder += "\n\n".join([s.generate_section(ctx) for s in sections])

        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Report</title>
        </head>
        <body>
        {builder}
        </body>
        </html>
        """

        fpath = get_report_directory(ctx) / ctx["final_report"]["file"]
        with open(fpath, 'w+') as fp:
            fp.write(full_html)
