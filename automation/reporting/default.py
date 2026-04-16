from typing import Any, Dict

from reporting.logger import ReportLog, ReportDataType
from reporting.sections import ReportSection
from workbench import get_workbench_path


class TranscriptSection(ReportSection):
    def __init__(self, index: int):
        super().__init__(index, 'Transcript')
        self.content = ""
        self.counter = 1

    def ingest_data(self, line: Any):
        if self.counter > 1:
            self.content += "\n"
        self.content += f"{self.counter}. {line}"
        self.counter += 1

    def body(self, ctx: Dict) -> str:
        return self.content

    def reset(self):
        self.content = ""
        self.counter = 1


class SuggestionSection(ReportSection):
    def __init__(self, index: int):
        super().__init__(index, 'Suggestion Report')
        self.content = ""

    def ingest_data(self, line: Any):
        if len(self.content) > 0:
            self.content += "\n"
        self.content += f"- {line}"

    def body(self, ctx: Dict) -> str:
        return self.content

    def reset(self):
        self.content = ""


class ModelReportSection(ReportSection):
    def __init__(self, index: int):
        super().__init__(index, 'Model Report')

    def _read_llm_report(self, ctx: Dict) -> str:
        fpath = get_workbench_path(ctx) / ctx['llm']['report_name']
        if not fpath.exists():
            return "LLM did not output a report"
        with open(fpath, 'r') as fp:
            return fp.read()

    def ingest_data(self, line: Any):
        pass

    def body(self, ctx: Dict) -> str:
        return self._read_llm_report(ctx)

    def reset(self):
        pass


class SimulationSection(ReportSection):
    def __init__(self, index: int):
        super().__init__(index, 'Simulation Report')
        self.runs = []

    def ingest_data(self, line: Any):
        self.runs.append(line)

    def reset(self):
        self.runs = []

    def body(self, ctx: Dict) -> str:
        pass


def create_default_report_sections(ctx: Dict, reporter: ReportLog):
    reporter.add_section(ReportDataType.TRANSCRIPT, TranscriptSection(0))
    reporter.add_section(ReportDataType.LLM_REPORT, ModelReportSection(1))
    reporter.add_section(ReportDataType.SUGGESTION, SuggestionSection(2))
    reporter.add_section(ReportDataType.SIMULATION, SimulationSection(3))
