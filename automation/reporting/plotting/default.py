from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
            ax.plot(x_sorted, x_sorted * m + b, label=f"Trend (R²: {r2:.2f})")

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
