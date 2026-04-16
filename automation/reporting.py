import logging
from pathlib import Path
from typing import Dict, Optional

from workbench import get_workbench_path


logger = logging.getLogger(__name__)


class ReportLog:
    def __init__(self):
        self.log = []
        self.suggestion_box = []

    def log_transcript(self, line: Optional[str]):
        if line is not None:
            self.log.append(line)

    def log_suggestion(self, suggestion: str):
        self.suggestion_box.append(suggestion)

    def generate_transcript(self) -> str:
        lines = [
            f"{i}: {line}"
            for i, line in enumerate(self.log)
        ]
        return '\n'.join(lines)

    def generate_suggestion_list(self) -> str:
        lines = [
            f"- {line}"
            for line in self.suggestion_box
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
        builder += "\n\n##Suggestion Report\n\n"
        builder += self.generate_suggestion_list()
        with open(fpath, 'w+') as fp:
            fp.write(builder)
