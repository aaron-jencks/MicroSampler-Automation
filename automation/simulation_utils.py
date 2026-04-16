import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from building import RunResult
from prompting.actions import LLMActionError, LLMActionResponse
from tools.args import SimulationArgs
from workbench import get_workbench_path


logger = logging.getLogger(__name__)


def get_data_directory(ctx: Dict, run_name: str) -> Path:
    return get_workbench_path(ctx) / ctx["workbench"]["data_directory"] / run_name


def handle_single_simulation_output(
        ctx: Dict, args: SimulationArgs,
        iteration: int,
        output: RunResult
) -> Tuple[List[Path], bool]:
    output_files = []

    log_prefix = get_data_directory(ctx, args.run_name)
    log_prefix.mkdir(parents=True, exist_ok=True)

    if args.stderr_file is not None and output.stderr is not None:
        err_file = log_prefix / args.stderr_file
        err_file = err_file.with_stem(f"{err_file.stem}-{iteration}")
        with open(err_file, mode='w+') as fp:
            fp.write(output.stderr)
        output_files.append(err_file)

    if output.errored:
        return output_files, True

    output_file_name = log_prefix / f"data-{iteration}.json"
    with open(output_file_name, mode='w+') as fp:
        fp.write(output.stdout)

    return output_files, False

def handle_simulation_output(
        ctx: Dict, args: SimulationArgs,
        outputs: List[RunResult]
) -> LLMActionResponse:
    logger.info('parsing run output')

    log_prefix = get_data_directory(ctx, args.run_name)
    log_prefix.mkdir(parents=True, exist_ok=True)

    result = LLMActionResponse("", None, None)

    output_files = []

    for iteration in range(args.global_iterations):
        output = outputs[iteration]
        files, errored = handle_single_simulation_output(ctx, args, iteration, output)
        output_files += files
        if errored:
            if output.timedout:
                result.error = LLMActionError(
                    "simulation timed out",
                    f"simulation took longer than {ctx['harness']['timeout']} seconds"
                )
            else:
                result.error = LLMActionError(
                    "simulation failed",
                    f"simulation failed with code: {output.return_code}\n"
                    f"stderr:\n```\n{output.stderr}\n```",
                )
            break

    result.response_message = "Output files:\n"
    result.response_message += "\n".join(map(str, output_files))

    return result


def get_simulation_dataframe(ctx: Dict, run_name: str) -> Optional[pd.DataFrame]:
    run_folder = get_data_directory(ctx, run_name)

    global_iterations = 0
    while True:
        data_file = run_folder / f"data-{global_iterations}.json"
        if not data_file.exists():
            break
        global_iterations += 1

    if global_iterations == 0:
        return None

    rows = []
    for gi in range(global_iterations):
        data_file = run_folder / f"data-{gi}.json"
        with open(data_file, mode='r') as fp:
            raw_data = json.load(fp)
        seed = raw_data["seed"]
        for row in raw_data["data"]:
            iteration = row["iteration"]
            for bit_data in row["durations"]:
                rows.append({
                    'random_seed': seed,
                    'global_iteration': gi,
                    'inner_iteration': iteration,
                    **bit_data
                })

    return pd.DataFrame(rows)
