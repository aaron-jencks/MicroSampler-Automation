from pathlib import Path
from typing import Any, Dict, Tuple
import uuid

import markdown
import pandas as pd

from reporting.logger import ReportLog, ReportDataType
from reporting.plotting.default import TimingScatterGenerator, GlobalTimingDistributionGenerator, \
    GlobalTimingDistributionBoxGenerator, TimingDistributionGenerator, TimingDistributionBoxGenerator, \
    GlobalTimingIterationHeatmapGenerator
from reporting.sections import ReportSection
from reporting.utils import get_report_directory
from simulation_utils import get_simulation_dataframe
from workbench import get_workbench_path


class ListSection(ReportSection):
    def __init__(self, index: int, name: str):
        super().__init__(index, name)
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

    def _do_global_distribution_plot(self, ctx: Dict, df: pd.DataFrame) -> Path:
        pname = self._generate_plot_filename(ctx)
        generator = GlobalTimingDistributionGenerator(pname)
        generator.generate_plot(ctx, df)
        return pname

    def _do_global_box_plot(self, ctx: Dict, df: pd.DataFrame) -> Path:
        pname = self._generate_plot_filename(ctx)
        generator = GlobalTimingDistributionBoxGenerator(pname)
        generator.generate_plot(ctx, df)
        return pname

    def _do_iteration_distribution_plots(self, ctx: Dict, df: pd.DataFrame, iteration: int) -> Tuple[Path, Path]:
        pname_dist = self._generate_plot_filename(ctx)
        pname_box = self._generate_plot_filename(ctx)
        dgen = TimingDistributionGenerator(iteration, pname_dist)
        dgen.generate_plot(ctx, df)
        bgen = TimingDistributionBoxGenerator(iteration, pname_box)
        bgen.generate_plot(ctx, df)
        return pname_dist, pname_box

    def _do_iteration_heatmap(self, ctx: Dict, df: pd.DataFrame) -> Path:
        pname = self._generate_plot_filename(ctx)
        generator = GlobalTimingIterationHeatmapGenerator(pname)
        generator.generate_plot(ctx, df)
        return pname

    def _format_image_line(self, ctx: Dict, name: str, p: Path) -> str:
        return f"![{name}]({str(p.relative_to(get_report_directory(ctx)))})"

    def _generate_iteration_distribution_table(self, df: pd.DataFrame) -> str:
        rows = [
            "| Iteration | Class | Samples | Mean | Median | Std Dev | Min | Max |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]

        grouped = (
            df.groupby(["inner_iteration", "class"])["duration"]
            .agg(["count", "mean", "median", "std", "min", "max"])
            .reset_index()
            .sort_values(["inner_iteration", "class"])
        )

        for _, row in grouped.iterrows():
            stddev = 0.0 if pd.isna(row["std"]) else row["std"]
            rows.append(
                f"| {int(row['inner_iteration'])} | {int(row['class'])} | {int(row['count'])} | "
                f"{row['mean']:.2f} | {row['median']:.2f} | {stddev:.2f} | {int(row['min'])} | {int(row['max'])} |"
            )

        return markdown.markdown("\n".join(rows), extensions=["tables"])

    def body(self, ctx: Dict) -> str:
        dfs = [
            get_simulation_dataframe(ctx, run)
            for run in self.runs
        ]
        global_df = pd.concat(dfs, ignore_index=True)
        images = [
            self._format_image_line(ctx, "iteration_versus_duration", self._do_global_iteration_plot(ctx, global_df)),
            self._format_image_line(ctx, "global_duration_distribution", self._do_global_distribution_plot(ctx, global_df)),
            self._format_image_line(ctx, "global_duration_boxplot", self._do_global_box_plot(ctx, global_df)),
            self._format_image_line(ctx, "global_duration_heatmap", self._do_iteration_heatmap(ctx, global_df)),
        ]
        global_images = '\n\n'.join(images)
        global_html = markdown.markdown(global_images)
        # dimg, bimg = self._do_iteration_distribution_plots(ctx, global_df, iteration)
        iteration_html = self._generate_iteration_distribution_table(global_df)
        return (f"<details><summary>Global Duration Distribution</summary>{global_html}</details>"
                f"<details><summary>Iteration Specific Distributions</summary>{iteration_html}</details>")


def create_default_report_sections(ctx: Dict, reporter: ReportLog):
    reporter.add_section(ReportDataType.TRANSCRIPT, ListSection(0, "Transcript"))
    reporter.add_section(ReportDataType.LLM_REPORT, ModelReportSection(1))
    reporter.add_section(ReportDataType.SUGGESTION, ListSection(2, "Suggestion Report"))
    reporter.add_section(ReportDataType.SIMULATION, SimulationSection(3))
