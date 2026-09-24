from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import defaultdict
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from common import CollatedData, TokenUsage

logger = logging.getLogger(__name__)


def generate_cascading_score_array(arr: List[List[float]], threshold: float = 0.95) -> np.ndarray:
    previous_size = None
    for ti in range(len(arr)):
        if previous_size is None:
            previous_size = len(arr[ti])
            continue
        if len(arr[ti]) < previous_size:
            diff = previous_size - len(arr[ti])
            padding = [threshold]*diff
            arr[ti].extend(padding)
    return np.array(arr)


def generate_array_stats(arr: List[List[float]]) -> Tuple[List[float], List[float], List[float]]:
    means = []
    mins = []
    maxes = []
    for sequence in arr:
        if len(sequence) == 0:
            means.append(0)
            mins.append(0)
            maxes.append(0)
            continue
        means.append(np.mean(sequence))
        mins.append(np.min(sequence))
        maxes.append(np.max(sequence))
    return means, mins, maxes


def generate_bar_plot_w_errors(ax, labels: List, values: List[List[float]], legend_label: str | None = None, bar_width: float | None = None):
    means, mins, maxes = generate_array_stats(values)
    kwargs: Dict[str, Any] = {
        "yerr": np.array([mins, maxes]),
        "error_kw": {
            "ecolor": (0, 0, 0, 0.5),
            "capsize": 5
        }
    }
    if legend_label is not None:
        kwargs["label"] = legend_label
    if bar_width is not None:
        kwargs["width"] = bar_width
    ax.bar(labels, means, **kwargs)


DATA_EXTRACTOR = Callable[[str, str], List[float]]


def generate_side_stacked_bar_plot(
        ax,
        x_labels: List[str], agent_labels: List[str],
        has_data: Callable[[str], bool],
        extractor: Callable[[str, str], List[float]],
        total_width: float = 2.0,
        empty_text: str = "No data found"
):
    if not any(map(has_data, x_labels)):
        ax.text(
            0.5, 0.5,
            empty_text,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return
    bar_width = total_width / len(agent_labels)
    x = np.arange(len(agent_labels))
    for ni, name in enumerate(x_labels):
        if has_data(name):
            values = [extractor(name, agent_name) for agent_name in agent_labels]
            generate_bar_plot_w_errors(ax, x + ni * bar_width, values, legend_label=name, bar_width=bar_width)
    ax.set_xticks(x)
    ax.set_xticklabels(agent_labels)


def generate_token_count_side_stacked_bar_plot(
        ax,
        token_usage: Dict[str, TokenUsage],
        agent_labels: List[str],
        total_width: float = 2.0,
):
    bar_width = total_width / len(agent_labels)
    x = np.arange(len(agent_labels))
    input_values = np.array([token_usage[agent_name].input_count for agent_name in agent_labels])
    generate_bar_plot_w_errors(ax, x, input_values, legend_label="Input", bar_width=bar_width)
    output_values = np.array([token_usage[agent_name].output_count for agent_name in agent_labels])
    generate_bar_plot_w_errors(ax, x + bar_width, output_values, legend_label="Output", bar_width=bar_width)
    total_values = input_values + output_values
    generate_bar_plot_w_errors(ax, x + 2 * bar_width, total_values, legend_label="Total", bar_width=bar_width)
    ax.set_xticks(x)
    ax.set_xticklabels(agent_labels)


def setup_plot(
        ax,
        title: str, x_title: str, y_title: str,
        legend: bool = True,
        y_log: bool = False,
):
    if y_log:
        ax.set_yscale("log")
        ax.grid(True, which="major", axis="y", linestyle="-", alpha=0.4, zorder=0)
        ax.grid(True, which="minor", axis="y", linestyle="--", alpha=0.2, zorder=0)
        ax.set_axisbelow(True)
    ax.set_title(title)
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    if legend:
        ax.legend()


def main():
    parser = ArgumentParser(
        description="Runs multiple configurations of the automation governor and evaluates their performance",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("collation_data", type=Path, help="path to collation_data.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    with open(args.collation_data, 'r') as fp:
        collation = CollatedData.model_validate(json.load(fp))
        stats = collation.results

    fig, axes = plt.subplots(3, 3, figsize=(20, 15), constrained_layout=True)

    for name, stat in stats.items():
        score_matrix = generate_cascading_score_array(stat.iteration_scores)
        logger.info(f"score matrix: {score_matrix.shape}")
        means, mins, maxes = map(np.array, generate_array_stats(stat.iteration_scores))
        lower_err = means - mins
        upper_err = maxes - means
        x = np.arange(len(means))
        axes[0, 0].errorbar(x, means, yerr=np.array([lower_err, upper_err]), fmt="o-", capsize=5, label=name)
        axes[0, 0].axhline(y=0.95, linestyle="--", color="r", label="Success Threshold")
    setup_plot(axes[0, 0], "Implementation Score Over Time", "Iteration", "Score (log)", y_log=True)

    names = list(stats.keys())

    # Iterations to success
    if len(names) > 1:
        values = [
            stats[name].success_iterations
            for name in names
        ]
        generate_bar_plot_w_errors(axes[0, 1], names, values)
    else:
        iterations = stats[names[0]].success_iterations
        axes[0, 1].hist(iterations, bins=min(20, max(iterations)))
    setup_plot(axes[0, 1], "Iterations to Success", "Configuration", "Iterations", legend=False)

    # Probability of success at k
    iteration_count = 0
    for name in names:
        nic = max(stats[name].success_iterations)
        if nic > iteration_count:
            iteration_count = nic

    values = defaultdict(lambda: np.zeros(iteration_count))
    for name in names:
        for succ in stats[name].success_iterations:
            values[name][succ:] += 1
        values[name] /= collation.candidate_iterations

    x = np.arange(iteration_count)
    bar_width = 1 / len(names)
    for ni, name in enumerate(names):
        axes[0, 2].plot(x + ni*bar_width, values[name], linestyle="-", marker='o', label=name)

    setup_plot(axes[0, 2], "Probability of Success", "Iteration", "Probability")

    # Token Usage
    agent_names = list(set(list(stats[names[0]].success_token_usage.keys()) + list(stats[names[0]].failure_token_usage.keys())))

    total_width = 1 / len(agent_names)

    if len(names) > 1:
        generate_side_stacked_bar_plot(
            axes[1, 0], names, agent_names,
            lambda name: len(stats[name].success_token_usage) > 0,
            lambda name, agent_name: stats[name].success_token_usage[agent_name].input_count,
            total_width=total_width
        )
        setup_plot(axes[1, 0], "Input Token Usage Upon Success", "Agent", "Tokens (log)", y_log=True)

        generate_side_stacked_bar_plot(
            axes[1, 1], names, agent_names,
            lambda name: len(stats[name].success_token_usage) > 0,
            lambda name, agent_name: stats[name].success_token_usage[agent_name].output_count,
            total_width=total_width
        )
        setup_plot(axes[1, 1], "Output Token Usage Upon Success", "Agent", "Tokens (log)", y_log=True)

        generate_side_stacked_bar_plot(
            axes[1, 2], names, agent_names,
            lambda name: len(stats[name].success_token_usage) > 0,
            lambda name, agent_name: np.array(stats[name].success_token_usage[agent_name].output_count) + np.array(
                stats[name].success_token_usage[agent_name].input_count),
            total_width=total_width
        )
        setup_plot(axes[1, 2], "Total Token Usage Upon Success", "Agent", "Tokens (log)", y_log=True)
    else:
        generate_token_count_side_stacked_bar_plot(axes[1, 0], stats["baseline"].success_token_usage, agent_names, total_width=total_width)
        setup_plot(axes[1, 0], "Token Usage Upon Success", "Agent", "Tokens (log)", y_log=True)

        input_tokens = []
        for agent_name in agent_names:
            input_tokens.extend(stats["baseline"].success_token_usage[agent_name].input_count)
        axes[1, 1].hist(input_tokens, bins=min(20, max(input_tokens)))
        setup_plot(axes[1, 1], "Input Token Distribution Upon Success", "Tokens", "Count (log)", y_log=True, legend=False)

        output_tokens = []
        for agent_name in agent_names:
            output_tokens.extend(stats["baseline"].success_token_usage[agent_name].output_count)
        axes[1, 2].hist(output_tokens, bins=min(20, max(output_tokens)))
        setup_plot(axes[1, 2], "Output Token Distribution Upon Success", "Tokens", "Count (log)", y_log=True, legend=False)

    if len(names) > 1:
        generate_side_stacked_bar_plot(
            axes[2, 0], names, agent_names,
            lambda name: len(stats[name].failure_token_usage) > 0,
            lambda name, agent_name: stats[name].failure_token_usage[agent_name].input_count,
            total_width=total_width
        )
        setup_plot(axes[2, 0], "Input Token Usage Upon Failure", "Agent", "Tokens (log)", y_log=True)

        generate_side_stacked_bar_plot(
            axes[2, 1], names, agent_names,
            lambda name: len(stats[name].failure_token_usage) > 0,
            lambda name, agent_name: stats[name].failure_token_usage[agent_name].output_count,
            total_width=total_width
        )
        setup_plot(axes[2, 1], "Output Token Usage Upon Failure", "Agent", "Tokens (log)", y_log=True)

        generate_side_stacked_bar_plot(
            axes[2, 2], names, agent_names,
            lambda name: len(stats[name].failure_token_usage) > 0,
            lambda name, agent_name: np.array(stats[name].failure_token_usage[agent_name].output_count) + np.array(
                stats[name].failure_token_usage[agent_name].input_count),
            total_width=total_width
        )
        setup_plot(axes[2, 2], "Total Token Usage Upon Failure", "Agent", "Tokens (log)", y_log=True)
    else:
        generate_token_count_side_stacked_bar_plot(axes[2, 0], stats["baseline"].failure_token_usage, agent_names, total_width=total_width)
        setup_plot(axes[2, 0], "Token Usage Upon Failure", "Agent", "Tokens (log)", y_log=True)

        input_tokens = []
        for agent_name in agent_names:
            input_tokens.extend(stats["baseline"].failure_token_usage[agent_name].input_count)
        axes[2, 1].hist(input_tokens, bins=min(20, max(input_tokens)))
        setup_plot(axes[2, 1], "Input Token Distribution Upon Failure", "Tokens", "Count (log)", y_log=True, legend=False)

        output_tokens = []
        for agent_name in agent_names:
            output_tokens.extend(stats["baseline"].failure_token_usage[agent_name].output_count)
        axes[2, 2].hist(output_tokens, bins=min(20, max(output_tokens)))
        setup_plot(axes[2, 2], "Output Token Distribution Upon Failure", "Tokens", "Count (log)", y_log=True, legend=False)

    plt.show()


if __name__ == "__main__":
    main()
