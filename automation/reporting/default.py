from pathlib import Path
from typing import Any, Dict
import uuid

import pandas as pd

from reporting.logger import ReportLog, ReportDataType
from reporting.plotting.default import TimingScatterGenerator
from reporting.sections import ReportSection
from reporting.utils import get_report_directory
from simulation_utils import get_simulation_dataframe
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

    def _generate_plot_filename(self, ctx: Dict) -> Path:
        return get_report_directory(ctx) / ctx["final_report"]["plots_prefix"] / f"{uuid.uuid4()}.png"

    def _do_global_iteration_plot(self, ctx: Dict, df: pd.DataFrame) -> Path:
        pname = self._generate_plot_filename(ctx)
        generator = TimingScatterGenerator(pname)
        generator.generate_plot(ctx, df)
        return pname

    def body(self, ctx: Dict) -> str:
        dfs = [
            get_simulation_dataframe(ctx, run)
            for run in self.runs
        ]
        global_df = pd.concat(dfs, ignore_index=True)
        builder = f"![iteration_versus_duration]({str(self._do_global_iteration_plot(ctx, global_df).relative_to(get_report_directory(ctx)))})"
        return builder


def create_default_report_sections(ctx: Dict, reporter: ReportLog):
    reporter.add_section(ReportDataType.TRANSCRIPT, TranscriptSection(0))
    reporter.add_section(ReportDataType.LLM_REPORT, ModelReportSection(1))
    reporter.add_section(ReportDataType.SUGGESTION, SuggestionSection(2))
    reporter.add_section(ReportDataType.SIMULATION, SimulationSection(3))
