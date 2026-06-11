import json
import logging
from pathlib import Path
from typing import List

import pandas as pd

from config import BaseConfig
from simulation.building import RunResult, deploy_harness, build_harness, verify_legal_code, RunConfiguration
from simulation.exceptions import SimulationTimeoutError, SimulationFailureError, BuildError, IllegalCodeError


logger = logging.getLogger(__file__)


def handle_simulation_output(
        ctx: BaseConfig, args: RunConfiguration,
        outputs: List[RunResult]
) -> pd.DataFrame:
    logger.info('parsing run output')

    output_rows = []

    for iteration in range(args.global_iterations):
        output = outputs[iteration]
        if output.errored:
            if output.timedout:
                raise SimulationTimeoutError(output, ctx["harness"]["timeout"])
            else:
                raise SimulationFailureError(output)
        raw_data = json.loads(output.stdout)
        seed = raw_data["seed"]
        for row in raw_data["data"]:
            inner_iteration = row["iteration"]
            for bit_data in row["durations"]:
                output_rows.append({
                    'run_name': args.run_name,
                    'random_seed': seed,
                    'global_iteration': iteration,
                    'inner_iteration': inner_iteration,
                    **bit_data
                })

    return pd.DataFrame(output_rows)


def write_attack_source(ctx: BaseConfig, src: str):
    if not verify_legal_code(ctx, src):
        raise IllegalCodeError(src)
    file_name = Path(ctx['harness']['prefix']) / ctx['harness']['target']
    with open(file_name, mode='w+') as fp:
        fp.write(src)
    build_status = build_harness(ctx)
    if build_status.return_code != 0:
        raise BuildError(build_status)


def run_simulation(ctx: BaseConfig, config: RunConfiguration) -> pd.DataFrame:
    build_result = build_harness(ctx)
    if build_result.return_code != 0:
        raise BuildError(build_result)
    results = deploy_harness(ctx, config)
    return handle_simulation_output(ctx, config, results)
