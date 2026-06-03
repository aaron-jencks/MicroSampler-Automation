import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, get_origin, get_args

from pydantic import BaseModel

from agents import Hypothesis, Implementation, Summarization
from prompting.templates import TemplateController
from simulation.struct import RunConfiguration

logger = logging.getLogger(__file__)


def template_insert_file(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(args[0])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    return f"{file_path.name if len(args) == 2 and args[1] else str(file_path)}\n```\n{data}\n```"


def template_insert_template(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    file_path = Path(ctx["llm"]["templates"]["files"][args[0]])
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    with open(file_path, "r") as file:
        data = file.read()
    processed_template = client.process_template(ctx, data)
    return processed_template


def template_insert_config_value(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = ctx
    for key in args:
        current = current[key]
    return repr(current)


def template_insert_allowed_references(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    result = []
    for reference in ctx["harness"]["allowed_references"]:
        result.append(f"- {reference}")
    return '\n'.join(result)


def template_insert_runtime_data(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    current = kwargs
    for key in args:
        current = current[key]
    return repr(current)


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


def template_insert_model(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if len(args) < 1:
        raise RuntimeError(f"Expected at least one argument, got {len(args)}")
    return describe_model(model_map[args[0]])


def format_run_configuration(run_configuration: RunConfiguration) -> str:
    return (f"\nRun Configuration:\n"
            f"Global Iterations: {run_configuration.global_iterations}\n"
            f"Inner Iterations: {run_configuration.inner_iterations}\n"
            f"Run Name: {run_configuration.run_name}\n"
            f"Random Seed: {run_configuration.random_seed}")


def template_insert_hypothesis(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    hyp = kwargs["current_hypothesis"]
    hypothesis_string = f"Hypothesis: {hyp.hypothesis}\n\nPrevious Implementation Feedback:\n\n"
    for bug in hyp.previous_implementation_bugs:
        hypothesis_string += f"- {bug}\n"
    hypothesis_string += format_run_configuration(hyp.run_configuration)
    return hypothesis_string


def template_insert_simulation_feedback(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if "feedback" not in kwargs or kwargs["feedback"] is None:
        return "None"
    return kwargs['feedback']


def template_insert_simulation_results(ctx: Dict, client: TemplateController, tag_name: str, args: List[str], kwargs: Optional[Dict[str, Any]]) -> str:
    if "stats" not in kwargs or kwargs["stats"] is None:
        return "None"
    return f"""## Distribution Information:
### Global Distribution:

{kwargs['stats'].global_distribution.to_markdown(index=False)}

### Iteration Distribution:

{kwargs['stats'].iteration_distribution.to_markdown(index=False)}

## Significance Tests:

### Global Welch T-Tests:

{kwargs['stats'].global_welch_ttest_data.to_markdown(index=False)}

### Iteration Welch T-Tests:

{kwargs['stats'].iteration_welch_ttest_data.to_markdown(index=False)}

## Performance Scores:

Global: {kwargs['stats'].global_score}
Iteration: {kwargs['stats'].iteration_score}"""


def add_default_template_tools_to_client(ctx: Dict, client: TemplateController):
    client.create_template_tool("source", template_insert_file)
    client.create_template_tool("template", template_insert_template)
    client.create_template_tool("config", template_insert_config_value)
    client.create_template_tool("allowed_references", template_insert_allowed_references)
    client.create_template_tool("runtime_data", template_insert_runtime_data)
    client.create_template_tool("model", template_insert_model)
    client.create_template_tool("hypothesis", template_insert_hypothesis)
    client.create_template_tool("sim_feedback", template_insert_simulation_feedback)
    client.create_template_tool("results", template_insert_simulation_results)
