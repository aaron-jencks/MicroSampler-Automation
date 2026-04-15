import logging
from pathlib import Path
from typing import Dict

from workbench import get_workbench_path


logger = logging.getLogger(__name__)


class ReportLog:
    def __init__(self):
        self.log = []

    def log_transcript(self, line: str):
        self.log.append(line)

    def generate_transcript(self) -> str:
        lines = [
            f"{i}: {line}"
            for i, line in enumerate(self.log)
        ]
        return '\n'.join(lines)

    def read_llm_report(self, ctx: Dict) -> str:
        fpath = get_workbench_path(ctx) / ctx['llm']['report_name']
        if not fpath.exists():
            return "LLM did not output a report"
        with open(fpath, 'r') as fp:
            return fp.read()

    def generate_report(self, ctx: Dict):
        logger.info(f'generating report to {ctx["final_report"]["file"]}')
        fpath = Path(ctx["general_prefix"]) / ctx["final_report"]["file"]
        builder = f"#{ctx['final_report']['run_name']} Final Report"
        builder += "\n\n##Transcript\n\n"
        builder += self.generate_transcript()
        builder += "\n\n##LLM Report\n\n"
        builder += self.read_llm_report(ctx)
        with open(fpath, 'w+') as fp:
            fp.write(builder)
