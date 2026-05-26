from typing import Any

import pandas as pd
from scipy.stats import ttest_ind


def calculate_distribution_stats(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    return (
        df.groupby(group_columns)["duration"]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
        .sort_values(group_columns)
    )


def perform_welch_test(sample_a: pd.Series, sample_b: pd.Series) -> tuple[float, float]:
    statistic, pvalue = ttest_ind(sample_a, sample_b, equal_var=False)
    return float(statistic), float(pvalue)


def generate_global_distribution_table(df: pd.DataFrame) -> pd.DataFrame:
    grouped = calculate_distribution_stats(df, ["class"])
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
    return pd.DataFrame(
        rows,
        columns=["Class", "Samples", "Mean", "Median", "Std Dev", "Min", "Max"]
    )


def generate_global_welch_ttest_table(df: pd.DataFrame) -> pd.DataFrame:
    class_zero = df[df["class"] == 0]["duration"]
    class_one = df[df["class"] == 1]["duration"]
    statistic, pvalue = perform_welch_test(class_zero, class_one)
    rows = [[
        int(class_zero.shape[0]),
        int(class_one.shape[0]),
        class_zero.mean(),
        class_one.mean(),
        statistic,
        pvalue,
        pvalue < 0.05,
    ]]
    return pd.DataFrame(
        rows,
        columns=["Class 0 Samples", "Class 1 Samples", "Class 0 Mean", "Class 1 Mean", "T-Statistic", "P-Value",
                 "Significant (p < 0.05)"]
    )


def generate_iteration_distribution_table(df: pd.DataFrame) -> pd.DataFrame:
    grouped = calculate_distribution_stats(df, ["inner_iteration", "class"])
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
    return pd.DataFrame(
        rows,
        columns=["Iteration", "Class", "Samples", "Mean", "Median", "Std Dev", "Min", "Max"],
    )


def generate_iteration_welch_ttest_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for iteration in sorted(df["inner_iteration"].unique()):
        subset = df[df["inner_iteration"] == iteration]
        class_zero = subset[subset["class"] == 0]["duration"]
        class_one = subset[subset["class"] == 1]["duration"]
        statistic, pvalue = perform_welch_test(class_zero, class_one)
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
    return pd.DataFrame(
        rows,
        columns=["Iteration", "Class 0 Samples", "Class 1 Samples", "Class 0 Mean", "Class 1 Mean", "T-Statistic",
                 "P-Value", "Significant (p < 0.05)"]
    )


def _format_value(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    headers = df.columns.tolist()
    header_row = '| ' + ' | '.join(headers) + ' |'
    separator_row = '| ' + " | ".join("---" for _ in headers) + " |"
    body_rows = [
        "| " + " | ".join(map(_format_value, values)) + " |"
        for values in df.itertuples(index=False)
    ]
    return "\n".join([
        header_row,
        separator_row,
        *body_rows,
    ])
