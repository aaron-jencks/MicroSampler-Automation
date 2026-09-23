from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import defaultdict
import json
import logging
from pathlib import Path
import subprocess as sp
import sys
from typing import List
import uuid

from tqdm import tqdm

from common import StatisticalAnalysisResults, TokenUsage, CollatedData
from config import parse_args, AutomationSettings


logger = logging.getLogger(__name__)


def run_configuration_instance(config: AutomationSettings, log_directory: Path, local_config: Path | None, verbose: bool) -> Path:
    performance_log = log_directory / "performance.json"
    output_log = log_directory / "output.log"

    args = [
        "python", str(config.executable),
        "--performance-log", str(performance_log.resolve().absolute()),
    ]
    if len(config.configs) > 0:
        args.append("--configs")
        args.extend(list(map(str, config.configs)))
    if local_config is not None:
        args.append(str(local_config.resolve().absolute()))
    if verbose:
        args.append("--verbose")

    logger.debug(f"running configuration: {args}")

    with open(output_log, "w+") as fp:
        proc = sp.Popen(
            args,
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            cwd=config.cwd,
            text=True
        )

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

            fp.write(line)
            fp.flush()

        if proc.wait() != 0:
            raise RuntimeError("Candidate instance crashed!")

    return performance_log


def run_configuration(config: AutomationSettings, log_directory: Path, iterations: int, local_config: Path | None, verbose: bool) -> List[Path]:
    logs = []
    for iteration in tqdm(range(iterations), desc=f"Running candidate {config.name}"):
        instance_log_directory = log_directory / f"iteration_{iteration:06d}"
        instance_log_directory.mkdir(parents=True, exist_ok=True)

        logs.append(run_configuration_instance(config, instance_log_directory, local_config=local_config, verbose=verbose))
    return logs


def generate_candidate_name(candidate: AutomationSettings) -> str:
    if candidate.name is not None:
        return candidate.name
    else:
        return '_'.join([p.stem for p in candidate.configs])


def compute_candidate_stats(candidate: List[Path]) -> StatisticalAnalysisResults:
    data = [json.loads(result.read_text()) for result in candidate]

    result = StatisticalAnalysisResults(
        iteration_scores=[],
        success_iterations=[],
        success_token_usage={},
        failure_token_usage={},
    )

    iteration_scores = defaultdict(list)
    for row in data:
        for event in row["timeline"]:
            if event["name"] == "Analysis":
                iteration = event["iteration"] - 1
                score = event["payload"]["global_data"]["score"]
                iteration_scores[iteration].append(score)
            if event["name"] == "Conclusion":
                if event["payload"]["is_early"]:
                    result.success_iterations.append(event["iteration"] - 1)
                    for agent in event["payload"]["token_usage"]:
                        usage = event["payload"]["token_usage"][agent]
                        if agent not in result.success_token_usage:
                            result.success_token_usage[agent] = TokenUsage()
                        result.success_token_usage[agent].input_count.append(usage["input_tokens"])
                        result.success_token_usage[agent].output_count.append(usage["output_tokens"])
                else:
                    for agent in event["payload"]["token_usage"]:
                        usage = event["payload"]["token_usage"][agent]
                        if agent not in result.failure_token_usage:
                            result.failure_token_usage[agent] = TokenUsage()
                        result.failure_token_usage[agent].input_count.append(usage["input_tokens"])
                        result.failure_token_usage[agent].output_count.append(usage["output_tokens"])

    result.iteration_scores = [iteration_scores[i] for i in range(len(iteration_scores))]

    return result


def main():
    parser = ArgumentParser(
        description="Runs multiple configurations of the automation governor and evaluates their performance",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-name", type=str, default=uuid.uuid4().hex, help="Name of the study")
    parser.add_argument("--force-redo", action="store_true", help="Force redo of the study")
    parser.add_argument("--use-local", type=Path, default=None, help="Use local config in addition to candidate configs")
    parser.add_argument("-o", "--output-file", type=Path, default=Path("./collated.json"), help="The location to store the collated results")
    args, config = parse_args(parser)

    parent_log_directory = config.performance_log_directory / args.run_name

    if not parent_log_directory.exists() or args.force_redo:
        parent_log_directory.mkdir(parents=True, exist_ok=True)

        logger.info("running baseline configuration")
        results = {
            "baseline": run_configuration(config.baseline, parent_log_directory / "baseline", config.candidate_iterations, local_config=args.use_local, verbose=args.verbose),
        }

        for candidate in tqdm(config.candidates, desc="Running candidate configurations"):
            name = candidate.name if candidate.name is not None else uuid.uuid4().hex
            results[name] = run_configuration(candidate, parent_log_directory / name, config.candidate_iterations, local_config=args.use_local, verbose=args.verbose)
    else:
        logger.info("using cached data")
        results = {}
        for r in parent_log_directory.iterdir():
            if not r.is_dir():
                continue
            results[r.name] = list(sorted(r.glob("iteration_*/performance.json")))

    logger.info("computing statistics")
    stats = {
        name: compute_candidate_stats(results[name])
        for name in results
    }

    collation = CollatedData(
        candidate_iterations=config.candidate_iterations,
        results=stats,
    )

    logger.info(f"saving results to {args.output_file}")
    with open(args.output_file, "w+") as fp:
        json.dump(collation.model_dump(), fp, indent=4)
    logger.info(f"wrote results to {args.output_file}")


if __name__ == "__main__":
    main()