import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, get_origin, get_args

import pandas as pd
from pydantic import BaseModel

from agents.responses import Hypothesis, Implementation, Summarization
from config import BaseConfig
from prompting.templates import TemplateController
from simulation.ccopy.struct import RunConfiguration
from stats import dataframe_to_markdown
from system import get_cache_information, read_cpuinfo

logger = logging.getLogger(__file__)


def template_insert_cpuinfo(ctx: BaseConfig, client: TemplateController, tab_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = read_cpuinfo(ctx)
    for key in args:
        current = current[key]
    return str(current)


def template_insert_cache_info(ctx: BaseConfig, client: TemplateController, tab_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    caches = get_cache_information(ctx)
    lines = ["CPU Cache Heirarchy:"]
    for cache in caches:
        lines.append(f"- {cache.name}:")
        lines.append(f"\t- Level: {cache.level}")
        lines.append(f"\t- Type: {cache.type}")
        lines.append(f"\t- Size: {cache.size}")
        lines.append(f"\t- Coherency Line Size: {cache.coherency_line_size}")
        lines.append(f"\t- Associativity: {cache.ways_of_associativity}")
        lines.append(f"\t- Sets: {cache.number_of_sets}")
        lines.append(f"\t- Shared CPUS: {cache.shared_cpu_list}")

    return "\n".join(lines)


def template_insert_file(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


# def template_insert_template(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
#     if len(args) < 1:
#         raise RuntimeError(f"Expected at least one argument, got {len(args)}")
#     file_path = Path(ctx.llm.templates.files[args[0]])
#     if not file_path.exists():
#         raise FileNotFoundError(file_path)
#     with open(file_path, "r") as file:
#         data = file.read()
#     processed_template = client.process_template(ctx, data)
#     return processed_template


def template_insert_config_value(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = ctx.model_dump()
    for key in args:
        current = current[key]
    return repr(current)


def template_insert_allowed_references(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    result = []
    for reference in ctx.harness.allowed_references:
        result.append(f"- {reference}")
    return '\n'.join(result)


def template_insert_runtime_data(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = kwargs
    for key in args:
        current = current[key]
    return str(current)


def format_type(t) -> str:
    origin = get_origin(t)

    if origin is None:
        return getattr(t, "__name__", str(t))

    if origin is list:
        return f"list[{format_type(get_args(t)[0])}]"

    if origin is dict:
        k, v = get_args(t)
        return f"dict[{format_type(k)}, {format_type(v)}]"

    return str(t)


def describe_model(model: type[BaseModel]) -> str:
    lines = [f"{model.__name__}:"]

    for name, field in model.model_fields.items():
        required = "required" if field.is_required() else "optional"

        desc = ""
        if field.description:
            desc = f" - {field.description}"

        lines.append(
            f"  - {name}: {format_type(field.annotation)} ({required}){desc}"
        )

    return "\n".join(lines)


model_map = {
    "hypothesis": Hypothesis,
    "implementation": Implementation,
    "summary": Summarization,
}


def template_insert_model(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    return describe_model(model_map[args[0]])


def format_run_configuration(run_configuration: RunConfiguration) -> str:
    return (f"\nRun Configuration:\n"
            f"Global Iterations: {run_configuration.global_iterations}\n"
            f"Inner Iterations: {run_configuration.inner_iterations}\n"
            f"Run Name: {run_configuration.run_name}\n"
            f"Random Seed: {run_configuration.random_seed}")


def template_insert_hypothesis(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    hyp = kwargs["current_hypothesis"]
    hypothesis_string = f"Hypothesis: {hyp.hypothesis}\n\nPrevious Implementation Feedback:\n\n"
    for bug in hyp.previous_implementation_bugs:
        hypothesis_string += f"- {bug}\n"
    hypothesis_string += format_run_configuration(hyp.run_configuration)
    return hypothesis_string


def template_insert_simulation_feedback(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if "feedback" not in kwargs or kwargs["feedback"] is None:
        return "None"
    return kwargs['feedback']


def _format_float(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.6f}"


def _summarize_iteration_welch(iteration_welch: pd.DataFrame) -> str:
    required = {"Iteration", "Score", "P-Value", "Significant (p < 0.05)", "Class 0 Mean", "Class 1 Mean"}
    if iteration_welch.empty or not required.issubset(iteration_welch.columns):
        return "Iteration Welch summary unavailable."

    score = iteration_welch["Score"]
    significant = iteration_welch["Significant (p < 0.05)"].astype(bool)
    top_by_score = iteration_welch.sort_values("Score", ascending=False).head(20)

    mean_diff_df = iteration_welch.copy()
    mean_diff_df["Abs Mean Difference"] = (
        mean_diff_df["Class 0 Mean"] - mean_diff_df["Class 1 Mean"]
    ).abs()
    mean_diff_df = mean_diff_df.sort_values("Abs Mean Difference", ascending=False).head(10)
    mean_diff_columns = [
        "Iteration",
        "Class 0 Samples",
        "Class 1 Samples",
        "Class 0 Mean",
        "Class 1 Mean",
        "P-Value",
        "Score",
        "Abs Mean Difference",
    ]
    mean_diff_columns = [c for c in mean_diff_columns if c in mean_diff_df.columns]

    return f"""## Iteration Welch Summary

Inner iterations analyzed: {int(iteration_welch["Iteration"].nunique())}
Significant iterations: {int(significant.sum())} / {int(len(iteration_welch))}
Max score: {_format_float(score.max())}
Mean score: {_format_float(score.mean())}
Median score: {_format_float(score.median())}
95th percentile score: {_format_float(score.quantile(0.95))}

## Top Iterations By Score

{dataframe_to_markdown(top_by_score)}

## Iterations With Largest Class Mean Difference

{dataframe_to_markdown(mean_diff_df[mean_diff_columns])}"""


def _summarize_iteration_distribution(iteration_distribution: pd.DataFrame) -> str:
    if iteration_distribution.empty or "Samples" not in iteration_distribution.columns:
        return "Iteration distribution summary unavailable."

    lines = [
        "## Iteration Distribution Summary",
        "",
        f"Minimum class samples in any iteration/class bucket: {int(iteration_distribution['Samples'].min())}",
        f"Maximum class samples in any iteration/class bucket: {int(iteration_distribution['Samples'].max())}",
    ]

    required = {"Iteration", "Class", "Mean"}
    if required.issubset(iteration_distribution.columns):
        pivot = iteration_distribution.pivot(index="Iteration", columns="Class", values="Mean")
        if 0 in pivot.columns and 1 in pivot.columns:
            mean_diff = (pivot[0] - pivot[1]).abs().rename("Abs Mean Difference").reset_index()
            top_diff = mean_diff.sort_values("Abs Mean Difference", ascending=False).head(10)
            lines.extend([
                "",
                "## Iteration Distribution Mean-Difference Summary",
                "",
                dataframe_to_markdown(top_diff),
            ])

    return "\n".join(lines)


def template_insert_simulation_results(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if "stats" not in kwargs or kwargs["stats"] is None:
        return "None"
    stats = kwargs["stats"]
    return f"""## Distribution Information:
### Global Distribution:

{dataframe_to_markdown(stats.global_distribution)}

## Significance Tests:

### Global Welch T-Tests:

{dataframe_to_markdown(stats.global_welch_ttest_data)}

## Performance Scores:

Global: {stats.global_score}
Iteration: {stats.iteration_score}

{_summarize_iteration_welch(stats.iteration_welch_ttest_data)}

{_summarize_iteration_distribution(stats.iteration_distribution)}"""


def template_insert_summary(ctx: BaseConfig, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if "summary" not in kwargs or kwargs["summary"] is None:
        return "None"
    result = f"""## Summary:
{kwargs['summary'].description}

## Suggestions:

{kwargs['summary'].suggestion}

## Failure Reasons:

{kwargs['summary'].failure_reason}

## Implementation Bugs:
"""
    for bug in kwargs['summary'].bugs:
        result += f"- {bug}\n"
    return result


def add_default_template_tools_to_client(ctx: BaseConfig, client: TemplateController):
    client.create_template_tool("source", template_insert_file)
    # client.create_template_tool("template", template_insert_template)
    client.create_template_tool("config", template_insert_config_value)
    client.create_template_tool("allowed_references", template_insert_allowed_references)
    client.create_template_tool("runtime_data", template_insert_runtime_data)
    client.create_template_tool("model", template_insert_model)
    client.create_template_tool("hypothesis", template_insert_hypothesis)
    client.create_template_tool("sim_feedback", template_insert_simulation_feedback)
    client.create_template_tool("results", template_insert_simulation_results)
    client.create_template_tool("summary", template_insert_summary)
    client.create_template_tool("cacheinfo", template_insert_cache_info)
    client.create_template_tool("cpuinfo", template_insert_cpuinfo)
