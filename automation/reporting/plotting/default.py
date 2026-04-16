from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas import DataFrame

from reporting.plotting.defs import PlotGenerator


class TimingScatterGenerator(PlotGenerator):
    def generate_plot(self, ctx: Dict, df: pd.DataFrame):
        fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True)
        runs = df["run_name"].unique()
        cmap = plt.cm.get_cmap('tab10', len(runs))

        # raw data
        for i, run in enumerate(runs):
            subset = df[(df["run_name"] == run) & (df["class"] == 0)]
            ax1.scatter(
                subset["inner_iteration"],
                subset["duration"],
                color=cmap(i),
                label=run,
            )

            subset = df[(df["run_name"] == run) & (df["class"] == 1)]
            ax2.scatter(
                subset["inner_iteration"],
                subset["duration"],
                color=cmap(i),
                label=run,
            )

        # trend lines
        def compute_trendline(ax, cls: int):
            x_sorted = np.sort(df[df["class"] == cls]["inner_iteration"].unique())
            xc = df[df["class"] == cls]["inner_iteration"].values
            yc = df[df["class"] == cls]["duration"].values
            m, b = np.polyfit(xc, yc, 1)
            y_pred = xc * m + b
            ss_res = np.sum((yc - y_pred)**2)
            ss_tot = np.sum((yc - np.mean(yc))**2)
            r2 = 1 - (ss_res / ss_tot)
            ax.plot(x_sorted, x_sorted * m + b, label=f"Trend (R²: {r2:.2f})", color='r')

        compute_trendline(ax1, 0)
        compute_trendline(ax2, 1)

        ax1.set_title("Class 0")
        ax2.set_title("Class 1")

        handles, labels = ax1.get_legend_handles_labels()  # Both plots have the same colors and labels
        fig.legend(handles, labels)
        fig.suptitle("Duration vs Iteration")
        fig.supxlabel("Iteration")
        fig.supylabel("Duration (ns)")

        fig.savefig(self.fname)
        plt.close(fig)


class TimingDistributionGenerator(PlotGenerator):
    def __init__(self, iteration: int, fname: Path):
        super().__init__(fname)
        self.iteration = iteration

    def _create_histogram(self, ax, y):
        mean = np.mean(y)
        std = np.std(y)
        ax.hist(y, bins=100)
        ax.axvline(mean, linestyle="--", label=f"Mean = {mean:.2f}")
        ax.axvline(mean + std, linestyle=":", label=f"+1σ = {mean + std:.2f}")
        ax.axvline(mean - std, linestyle=":", label=f"-1σ = {mean - std:.2f}")
        ax.legend()

    def generate_plot(self, ctx: Dict, df: DataFrame):
        fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True)
        self._create_histogram(ax1, df[(df["class"] == 0) & (df["inner_iteration"] == self.iteration)]["duration"])
        self._create_histogram(ax2, df[(df["class"] == 1) & (df["inner_iteration"] == self.iteration)]["duration"])
        ax1.set_title("Class 0")
        ax2.set_title("Class 1")
        fig.suptitle(f"Duration Distribution of Iteration {self.iteration}")
        fig.supxlabel("Duration (ns)")
        fig.supylabel("Frequency")
        fig.savefig(self.fname)
        plt.close(fig)


class GlobalTimingDistributionGenerator(PlotGenerator):
    def _create_histogram(self, ax, y):
        mean = np.mean(y)
        std = np.std(y)
        ax.hist(y, bins=100)
        ax.axvline(mean, linestyle="--", label=f"Mean = {mean:.2f}")
        ax.axvline(mean + std, linestyle=":", label=f"+1σ = {mean + std:.2f}")
        ax.axvline(mean - std, linestyle=":", label=f"-1σ = {mean - std:.2f}")
        ax.legend()

    def generate_plot(self, ctx: Dict, df: DataFrame):
        fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True)
        self._create_histogram(ax1, df[df["class"] == 0]["duration"])
        self._create_histogram(ax2, df[df["class"] == 1]["duration"])
        ax1.set_title("Class 0")
        ax2.set_title("Class 1")
        fig.suptitle(f"Duration Distribution")
        fig.supxlabel("Duration (ns)")
        fig.supylabel("Frequency")
        fig.savefig(self.fname)
        plt.close(fig)


class TimingDistributionBoxGenerator(PlotGenerator):
    def __init__(self, iteration: int, fname: Path):
        super().__init__(fname)
        self.iteration = iteration

    def generate_plot(self, ctx: Dict, df: DataFrame):
        fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True)
        ax1.boxplot(df[(df["class"] == 0) & (df["inner_iteration"] == self.iteration)]["duration"])
        ax2.boxplot(df[(df["class"] == 1) & (df["inner_iteration"] == self.iteration)]["duration"])
        ax1.set_title("Class 0")
        ax2.set_title("Class 1")
        fig.suptitle(f"Duration Distribution of Iteration {self.iteration}")
        fig.supxlabel("Duration (ns)")
        fig.supylabel("Frequency")
        fig.savefig(self.fname)
        plt.close(fig)


class GlobalTimingDistributionBoxGenerator(PlotGenerator):
    def generate_plot(self, ctx: Dict, df: DataFrame):
        fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True)
        ax1.boxplot(df[df["class"] == 0]["duration"])
        ax2.boxplot(df[df["class"] == 1]["duration"])
        ax1.set_title("Class 0")
        ax2.set_title("Class 1")
        fig.suptitle(f"Duration Distribution")
        fig.supxlabel("Duration (ns)")
        fig.supylabel("Frequency")
        fig.savefig(self.fname)
        plt.close(fig)


class GlobalTimingIterationHeatmapGenerator(PlotGenerator):
    def generate_plot(self, ctx: Dict, df: DataFrame):
        heatmap_df_0 = df[df["class"] == 0].pivot_table(
            index="duration",
            columns="inner_iteration",
            aggfunc="size",
            fill_value=0
        )
        heatmap_df_1 = df[df["class"] == 1].pivot_table(
            index="duration",
            columns="inner_iteration",
            aggfunc="size",
            fill_value=0
        )
        fig, (ax1, ax2) = plt.subplots(1, 2)
        cax = ax1.imshow(heatmap_df_0, aspect="auto", origin="lower")
        fig.colorbar(cax, orientation="vertical", ax=ax1)
        cax = ax2.imshow(heatmap_df_1, aspect="auto", origin="lower")
        fig.colorbar(cax, orientation="vertical", ax=ax2)
        ax1.set_title("Class 0")
        ax2.set_title("Class 1")

        y_vals = heatmap_df_0.index
        tick_idx = np.linspace(0, len(y_vals)-1, 10, dtype=int)
        ax1.set_yticks(tick_idx)
        ax1.set_yticklabels(y_vals[tick_idx])

        y_vals = heatmap_df_1.index
        tick_idx = np.linspace(0, len(y_vals) - 1, 10, dtype=int)
        ax2.set_yticks(tick_idx)
        ax2.set_yticklabels(y_vals[tick_idx])

        fig.suptitle(f"Duration Distribution")
        fig.supylabel("Duration (ns)")
        fig.supxlabel("Iteration")
        fig.tight_layout(pad=2.0)
        fig.savefig(self.fname)
        plt.close(fig)
