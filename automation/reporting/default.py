from pathlib import Path
from typing import Any, Dict, Tuple
import uuid

import markdown
import pandas as pd
from scipy.stats import ttest_ind

from reporting.logger import ReportLog, ReportDataType
from reporting.plotting.default import TimingScatterGenerator, GlobalTimingDistributionGenerator, \
    GlobalTimingDistributionBoxGenerator, TimingDistributionGenerator, TimingDistributionBoxGenerator, \
    GlobalTimingIterationHeatmapGenerator
from reporting.sections import ReportSection
from reporting.tables import MarkdownTableBuilder
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
        self.table_builder = MarkdownTableBuilder()

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

    def _calculate_distribution_stats(self, df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
        return (
            df.groupby(group_columns)["duration"]
            .agg(["count", "mean", "median", "std", "min", "max"])
            .reset_index()
            .sort_values(group_columns)
        )

    def _perform_welch_test(self, sample_a: pd.Series, sample_b: pd.Series) -> tuple[float, float]:
        statistic, pvalue = ttest_ind(sample_a, sample_b, equal_var=False)
        return float(statistic), float(pvalue)

    def _generate_global_distribution_table(self, df: pd.DataFrame) -> str:
        grouped = self._calculate_distribution_stats(df, ["class"])
        rows = []
        for _, row in grouped.iterrows():
            stddev = 0.0 if pd.isna(row["std"]) else row["std"]
            rows.append([
                int(row["class"]),
                int(row["count"]),
                row["mean"],
                row["median"],
                stddev,
                int(row["min"]),
                int(row["max"]),
            ])
        return self.table_builder.to_html(
            ["Class", "Samples", "Mean", "Median", "Std Dev", "Min", "Max"],
            rows,
        )

    def _generate_global_welch_ttest_table(self, df: pd.DataFrame) -> str:
        class_zero = df[df["class"] == 0]["duration"]
        class_one = df[df["class"] == 1]["duration"]
        statistic, pvalue = self._perform_welch_test(class_zero, class_one)
        rows = [[
            int(class_zero.shape[0]),
            int(class_one.shape[0]),
            class_zero.mean(),
            class_one.mean(),
            statistic,
            pvalue,
            pvalue < 0.05,
        ]]
        return self.table_builder.to_html(
            ["Class 0 Samples", "Class 1 Samples", "Class 0 Mean", "Class 1 Mean", "T-Statistic", "P-Value", "Significant (p < 0.05)"],
            rows,
        )

    def _generate_iteration_distribution_table(self, df: pd.DataFrame) -> str:
        grouped = self._calculate_distribution_stats(df, ["inner_iteration", "class"])
        rows = []
        for _, row in grouped.iterrows():
            stddev = 0.0 if pd.isna(row["std"]) else row["std"]
            rows.append([
                int(row["inner_iteration"]),
                int(row["class"]),
                int(row["count"]),
                row["mean"],
                row["median"],
                stddev,
                int(row["min"]),
                int(row["max"]),
            ])
        return self.table_builder.to_html(
            ["Iteration", "Class", "Samples", "Mean", "Median", "Std Dev", "Min", "Max"],
            rows,
        )

    def _generate_iteration_welch_ttest_table(self, df: pd.DataFrame) -> str:
        rows = []
        for iteration in sorted(df["inner_iteration"].unique()):
            subset = df[df["inner_iteration"] == iteration]
            class_zero = subset[subset["class"] == 0]["duration"]
            class_one = subset[subset["class"] == 1]["duration"]
            statistic, pvalue = self._perform_welch_test(class_zero, class_one)
            rows.append([
                int(iteration),
                int(class_zero.shape[0]),
                int(class_one.shape[0]),
                class_zero.mean(),
                class_one.mean(),
                statistic,
                pvalue,
                pvalue < 0.05,
            ])
        return self.table_builder.to_html(
            ["Iteration", "Class 0 Samples", "Class 1 Samples", "Class 0 Mean", "Class 1 Mean", "T-Statistic", "P-Value", "Significant (p < 0.05)"],
            rows,
        )

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
        global_stats_html = self._generate_global_distribution_table(global_df)
        global_welch_html = self._generate_global_welch_ttest_table(global_df)
        iteration_stats_html = self._generate_iteration_distribution_table(global_df)
        iteration_welch_html = self._generate_iteration_welch_ttest_table(global_df)
        return (
            f"<details><summary>Global Duration Distribution</summary>"
            f"{global_welch_html}{global_stats_html}{global_html}</details>"
            f"<details><summary>Iteration Specific Distributions</summary>"
            f"{iteration_welch_html}{iteration_stats_html}</details>"
        )


def create_default_report_sections(ctx: Dict, reporter: ReportLog):
    reporter.add_section(ReportDataType.TRANSCRIPT, ListSection(0, "Transcript"))
    reporter.add_section(ReportDataType.LLM_REPORT, ModelReportSection(1))
    reporter.add_section(ReportDataType.SUGGESTION, ListSection(2, "Suggestion Report"))
    reporter.add_section(ReportDataType.SIMULATION, SimulationSection(3))
