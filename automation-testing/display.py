from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import defaultdict
import json
import logging
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from common import CollatedData


logger = logging.getLogger(__name__)


def generate_array_stats(arr: List[List[float]]) -> Tuple[List[float], List[float], List[float]]:
    means = []
    mins = []
    maxes = []
    for sequence in arr:
        means.append(np.mean(sequence))
        mins.append(np.min(sequence))
        maxes.append(np.max(sequence))
    return means, mins, maxes


def generate_bar_plot_w_errors(ax, labels: List, values: List[List[float]], legend_label: str | None = None):
    means, mins, maxes = generate_array_stats(values)
    if legend_label is None:
        ax.bar(labels, means, yerr=np.array([mins, maxes]))
    else:
        ax.bar(labels, means, yerr=np.array([mins, maxes]), label=legend_label)


def main():
    parser = ArgumentParser(
        description="Runs multiple configurations of the automation governor and evaluates their performance",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("collation_data", type=Path, help="path to collation_data.json")
    args = parser.parse_args()

    with open(args.collation_data, 'r') as fp:
        collation = CollatedData.model_validate(json.load(fp))
        stats = collation.results

    fig, axes = plt.subplots(3, 3, figsize=(20, 15))

    for name, stat in stats.items():
        means = []
        mins = []
        maxes = []
        for iteration in stat.iteration_scores:
            means.append(np.mean(iteration))
            mins.append(np.min(iteration))
            maxes.append(np.max(iteration))
        axes[0, 0].plot(means, yerr=np.array([mins, maxes]), label=name)
    axes[0, 0].set_title("Implementation Score Over Time")
    axes[0, 0].set_xlabel("Iteration")
    axes[0, 0].set_ylabel("Score")
    axes[0, 0].legend()

    names = list(stats.keys())

    # Iterations to success
    values = [
        stats[name].success_iterations
        for name in names
    ]
    generate_bar_plot_w_errors(axes[0, 1], names, values)
    axes[0, 1].set_title("Iterations to Success")
    axes[0, 1].set_xlabel("Configuration")
    axes[0, 1].set_ylabel("Iterations")

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
        values[name] /= config.candidate_iterations

    x = np.arange(iteration_count)
    total_width = 0.15*len(names)
    for ni, name in enumerate(names):
        axes[0, 2].bar(x + ni*0.15, values[name], total_width, label=name)

    axes[0, 2].set_title("Probability of Success")
    axes[0, 2].set_ylabel("Probability")
    axes[0, 2].set_xlabel("Iteration")
    axes[0, 2].legend()

    # Token Usage
    agent_names = list(set(list(stats[names[0]].success_token_usage.keys()) + list(stats[names[0]].failure_token_usage.keys())))

    total_width = 2.0
    bar_width = total_width / len(agent_names)

    x = np.arange(len(agent_names))

    for ni, name in enumerate(names):
        values = [stats[name].success_token_usage[agent_name].input_count for agent_name in agent_names]
        generate_bar_plot_w_errors(axes[1, 0], x + ni * bar_width, values, legend_label=name)
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(agent_names)
    axes[1, 0].set_title("Input Token Usage Upon Success")
    axes[1, 0].set_ylabel("Token Usage")
    axes[1, 0].set_xlabel("Agent")
    axes[1, 0].legend()

    for ni, name in enumerate(names):
        values = [stats[name].success_token_usage[agent_name].output_count for agent_name in agent_names]
        generate_bar_plot_w_errors(axes[1, 1], x + ni * bar_width, values, legend_label=name)
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(agent_names)
    axes[1, 1].set_title("Output Token Usage Upon Success")
    axes[1, 1].set_ylabel("Token Usage")
    axes[1, 1].set_xlabel("Agent")
    axes[1, 1].legend()

    for ni, name in enumerate(names):
        values = [
            np.array(stats[name].success_token_usage[agent_name].output_count) + np.array(stats[name].success_token_usage[agent_name].input_count)
            for agent_name in agent_names
        ]
        generate_bar_plot_w_errors(axes[1, 2], x + ni * bar_width, values, legend_label=name)
    axes[1, 2].set_xticks(x)
    axes[1, 2].set_xticklabels(agent_names)
    axes[1, 2].set_title("Total Token Usage Upon Success")
    axes[1, 2].set_ylabel("Token Usage")
    axes[1, 2].set_xlabel("Agent")
    axes[1, 2].legend()

    for ni, name in enumerate(names):
        values = [stats[name].failure_token_usage[agent_name].input_count for agent_name in agent_names]
        generate_bar_plot_w_errors(axes[2, 0], x + ni * bar_width, values, legend_label=name)
    axes[2, 0].set_xticks(x)
    axes[2, 0].set_xticklabels(agent_names)
    axes[2, 0].set_title("Input Token Usage Upon Failure")
    axes[2, 0].set_ylabel("Token Usage")
    axes[2, 0].set_xlabel("Agent")
    axes[2, 0].legend()

    for ni, name in enumerate(names):
        values = [stats[name].failure_token_usage[agent_name].output_count for agent_name in agent_names]
        generate_bar_plot_w_errors(axes[2, 1], x + ni * bar_width, values, legend_label=name)
    axes[2, 1].set_xticks(x)
    axes[2, 1].set_xticklabels(agent_names)
    axes[2, 1].set_title("Output Token Usage Upon Failure")
    axes[2, 1].set_ylabel("Token Usage")
    axes[2, 1].set_xlabel("Agent")
    axes[2, 1].legend()

    for ni, name in enumerate(names):
        values = [
            np.array(stats[name].failure_token_usage[agent_name].output_count) + np.array(stats[name].failure_token_usage[agent_name].input_count)
            for agent_name in agent_names
        ]
        generate_bar_plot_w_errors(axes[2, 2], x + ni * bar_width, values, legend_label=name)
    axes[2, 2].set_xticks(x)
    axes[2, 2].set_xticklabels(agent_names)
    axes[2, 2].set_title("Total Token Usage Upon Failure")
    axes[2, 2].set_ylabel("Token Usage")
    axes[2, 2].set_xlabel("Agent")
    axes[2, 2].legend()


if __name__ == "__main__":
    main()