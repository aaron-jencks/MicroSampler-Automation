import argparse
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any, Dict

from reporting.default import create_default_report_sections
from reporting.logger import ReportLog
from tools.defs import (
    AttackFileCreate,
    MakeConclusion,
    RunSimulation,
    SuggestionBox,
    WorkbenchDeleteFile,
    WorkbenchFileCreate,
    WorkbenchListFiles,
    WorkbenchReadFile,
    WorkbenchReset,
    WorkbenchRun,
)
from workbench import get_workbench_path, reset_workbench


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
SMOKE_DATA = ROOT / "smoke_data"
ATTACK_TEMPLATE = SMOKE_DATA / "attack-stub.c"
WORKBENCH_TEMPLATE = SMOKE_DATA / "workbench-smoke.sh"


class SmokeFailure(RuntimeError):
    pass


def setup_logging(ctx: Dict):
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    )

    log_path = Path(ctx["logging"]["prefix"]) / ctx["logging"]["output"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = log_path.with_stem(log_path.stem + "_" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))

    file = logging.FileHandler(log_path)
    file.setLevel(logging.DEBUG)
    file.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file)


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_configs(cfgs, default: Path) -> Dict:
    with open(default, "r") as fp:
        conf = json.load(fp)
    for cfg in cfgs:
        with open(cfg, "r") as fp:
            conf = merge_dicts(conf, json.load(fp))
    return conf


def ensure(condition: bool, message: str):
    if not condition:
        raise SmokeFailure(message)


def expected_workbench_path(ctx: Dict, fname: str) -> Path:
    return get_workbench_path(ctx) / fname


def report_path(ctx: Dict) -> Path:
    return Path(ctx["final_report"]["prefix"]) / ctx["final_report"]["run_name"] / ctx["final_report"]["file"]


def report_plots_path(ctx: Dict) -> Path:
    return Path(ctx["final_report"]["prefix"]) / ctx["final_report"]["run_name"] / ctx["final_report"]["plots_prefix"]


def harness_attack_path(ctx: Dict) -> Path:
    return Path(ctx["harness"]["prefix"]) / ctx["harness"]["target"]


def load_template(path: Path) -> str:
    ensure(path.exists(), f"missing smoke template: {path}")
    return path.read_text()


def run_action(action, ctx: Dict, payload: Dict[str, Any], label: str):
    logger.info("smoke step: %s", label)
    args = action.schema.model_validate(payload)
    response = action.execute(ctx, args)
    if response.error is not None:
        raise SmokeFailure(
            f"{label} failed: {response.error.name}: {response.error.description}"
        )
    print(f"[PASS] {label}")
    return response


def expect_action_error(action, ctx: Dict, payload: Dict[str, Any], label: str, error_name: str):
    logger.info("smoke step: %s", label)
    args = action.schema.model_validate(payload)
    response = action.execute(ctx, args)
    ensure(response.error is not None, f"{label} unexpectedly succeeded")
    ensure(response.error.name == error_name, f"{label} returned wrong error: {response.error.name}")
    print(f"[PASS] {label}")
    return response


def create_actions(ctx: Dict, reporter: ReportLog) -> Dict[str, Any]:
    return {
        "create": WorkbenchFileCreate(reporter),
        "read": WorkbenchReadFile(reporter),
        "delete": WorkbenchDeleteFile(reporter),
        "list": WorkbenchListFiles(reporter),
        "run": WorkbenchRun(ctx, reporter),
        "reset": WorkbenchReset(reporter),
        "attack": AttackFileCreate(reporter),
        "simulate": RunSimulation(ctx, reporter),
        "suggest": SuggestionBox(reporter),
        "conclude": MakeConclusion(reporter),
    }


def run_crud_checks(ctx: Dict, actions: Dict[str, Any]):
    test_file = "notes/smoke.txt"
    test_contents = "smoke-test file contents\nline two\n"
    expected_path = expected_workbench_path(ctx, test_file)

    run_action(actions["create"], ctx, {
        "reasoning": "Create a normal workbench file and verify on-disk placement.",
        "file_name": test_file,
        "file_contents": test_contents,
    }, "workbench_create_file")
    ensure(expected_path.exists(), f"created file missing: {expected_path}")
    ensure(expected_path.read_text() == test_contents, "created file contents did not match")

    read_response = run_action(actions["read"], ctx, {
        "reasoning": "Read back the file that was just created.",
        "file_name": test_file,
    }, "workbench_read_file")
    ensure(read_response.response_message == test_contents, "read file contents did not match")

    list_response = run_action(actions["list"], ctx, {
        "reasoning": "Confirm the created file appears in the workbench listing.",
    }, "workbench_list_files")
    listed_files = set(filter(None, (list_response.response_message or "").splitlines()))
    ensure(str(expected_path) in listed_files, "created file missing from workbench listing")

    run_action(actions["delete"], ctx, {
        "reasoning": "Delete the created workbench file.",
        "file_name": test_file,
    }, "workbench_delete_file")
    ensure(not expected_path.exists(), f"deleted file still exists: {expected_path}")

    expect_action_error(actions["read"], ctx, {
        "reasoning": "Confirm the deleted file cannot be read.",
        "file_name": test_file,
    }, "workbench_read_file_missing", "file not found")

    list_response = run_action(actions["list"], ctx, {
        "reasoning": "Confirm the deleted file no longer appears in the workbench listing.",
    }, "workbench_list_files_after_delete")
    listed_files = set(filter(None, (list_response.response_message or "").splitlines()))
    ensure(str(expected_path) not in listed_files, "deleted file still present in workbench listing")


def run_reset_checks(ctx: Dict, actions: Dict[str, Any]):
    normal_file = "reset-check/ephemeral.txt"
    data_file = f"{ctx['workbench']['data_directory']}/persist/keep.json"
    normal_path = expected_workbench_path(ctx, normal_file)
    data_path = expected_workbench_path(ctx, data_file)
    source_prefix = expected_workbench_path(ctx, ctx["workbench"]["source"]["prefix"])

    run_action(actions["create"], ctx, {
        "reasoning": "Create a normal file to verify reset cleanup.",
        "file_name": normal_file,
        "file_contents": "ephemeral\n",
    }, "workbench_create_file_for_reset")
    run_action(actions["create"], ctx, {
        "reasoning": "Create data under the workbench data directory to test flush behavior.",
        "file_name": data_file,
        "file_contents": "{\"preserve\": true}\n",
    }, "workbench_create_data_file")

    ensure(normal_path.exists(), "reset precondition failed: normal file missing")
    ensure(data_path.exists(), "reset precondition failed: data file missing")

    run_action(actions["reset"], ctx, {
        "reasoning": "Reset the workbench while preserving cached data.",
        "flush_data": False,
    }, "workbench_reset_keep_data")
    ensure(not normal_path.exists(), "workbench reset did not remove normal file")
    ensure(data_path.exists(), "workbench reset unexpectedly removed data with flush_data=False")
    ensure(source_prefix.exists(), "workbench source prefix missing after reset")
    for key in ctx["workbench"]["source"]["contents"]:
        ensure((source_prefix / key).exists(), f"workbench source tree missing after reset: {key}")

    run_action(actions["reset"], ctx, {
        "reasoning": "Reset the workbench and flush cached data.",
        "flush_data": True,
    }, "workbench_reset_flush_data")
    ensure(not data_path.exists(), "workbench reset did not remove data with flush_data=True")


def run_workbench_script_check(ctx: Dict, actions: Dict[str, Any]):
    script_name = ctx["workbench"]["script"]
    script_contents = load_template(WORKBENCH_TEMPLATE)
    output_file = expected_workbench_path(ctx, "script-output.txt")

    run_action(actions["create"], ctx, {
        "reasoning": "Install the smoke workbench script template before running it.",
        "file_name": script_name,
        "file_contents": script_contents,
    }, "workbench_create_script_template")
    ensure(expected_workbench_path(ctx, script_name).read_text() == script_contents, "workbench script template write failed")

    run_response = run_action(actions["run"], ctx, {
        "reasoning": "Execute the smoke workbench script and inspect its outputs.",
        "args": ["alpha", "beta", "gamma"],
    }, "workbench_run")
    run_output = run_response.response_message or ""
    ensure("workbench smoke script" in run_output, "workbench run output missing stdout marker")
    ensure("script invoked with 3 args" in run_output, "workbench run output missing stderr marker")
    ensure(output_file.exists(), "workbench script did not create its output file")
    ensure(output_file.read_text() == "alpha beta gamma\n", "workbench script output file contents did not match")


def run_attack_and_simulation_checks(ctx: Dict, actions: Dict[str, Any], reporter: ReportLog):
    attack_contents = load_template(ATTACK_TEMPLATE)
    attack_path = harness_attack_path(ctx)

    run_action(actions["attack"], ctx, {
        "reasoning": "Write a known-good attack stub through the real AttackFileCreate action.",
        "attack_contents": attack_contents,
    }, "create_attack_file")
    ensure(attack_path.exists(), f"attack file missing after AttackFileCreate: {attack_path}")
    ensure(attack_path.read_text() == attack_contents, "attack file contents did not match the template")
    ensure(reporter.simulation_count == 0, "simulation counter was not cleared by AttackFileCreate")

    sim_response = run_action(actions["simulate"], ctx, {
        "reasoning": "Run a short deterministic simulation to validate deployment and output handling.",
        "global_iterations": 10,
        "inner_iterations": 100,
        "random_seed": 12345,
        "run_name": "smoke-run",
        "stderr_file": "stderr.log",
    }, "run_simulation")

    data_root = expected_workbench_path(ctx, f"{ctx['workbench']['data_directory']}/smoke-run")
    ensure(data_root.exists(), f"simulation output directory missing: {data_root}")
    for index in range(2):
        data_file = data_root / f"data-{index}.json"
        stderr_file = data_root / f"stderr-{index}.log"
        ensure(data_file.exists(), f"simulation data file missing: {data_file}")
        ensure(stderr_file.exists(), f"simulation stderr file missing: {stderr_file}")
        with open(data_file, "r") as fp:
            json.load(fp)
    ensure("Output files:" in (sim_response.response_message or ""), "simulation response missing output summary")
    ensure(reporter.simulation_count > 0, "simulation counter was not incremented")


def run_reporting_checks(ctx: Dict, actions: Dict[str, Any], reporter: ReportLog):
    llm_report_contents = "# Smoke Conclusion\n\nSynthetic report body.\n"
    suggestion_text = "Keep this deterministic smoke path as a regression gate."

    run_action(actions["create"], ctx, {
        "reasoning": "Create the synthetic model report file for final report generation.",
        "file_name": ctx["llm"]["report_name"],
        "file_contents": llm_report_contents,
    }, "workbench_create_llm_report")

    run_action(actions["suggest"], ctx, {
        "reasoning": "Exercise the suggestion box action for report coverage.",
        "suggestion": suggestion_text,
    }, "suggestion_box")

    conclusion_response = run_action(actions["conclude"], ctx, {
        "reasoning": "Finish the smoke run after a successful simulation.",
        "constant_time": True,
    }, "make_conclusion")
    ensure(conclusion_response.conclusion is not None, "make_conclusion did not return a conclusion")
    ensure(conclusion_response.conclusion.constant_time is True, "unexpected conclusion value")

    report_plots_path(ctx).mkdir(parents=True, exist_ok=True)
    reporter.generate_report(ctx)

    final_report = report_path(ctx)
    ensure(final_report.exists(), f"final report was not generated: {final_report}")
    report_text = final_report.read_text()
    ensure("<summary>Transcript</summary>" in report_text, "final report missing transcript section")
    ensure("<summary>Model Report</summary>" in report_text, "final report missing model report section")
    ensure("<summary>Suggestion Report</summary>" in report_text, "final report missing suggestion section")
    ensure("<summary>Simulation Report</summary>" in report_text, "final report missing simulation section")
    ensure("Synthetic report body." in report_text, "final report missing synthetic model report text")
    ensure(suggestion_text in report_text, "final report missing suggestion text")
    print("[PASS] generate_report")


def main(ctx: Dict):
    ensure(ATTACK_TEMPLATE.exists(), f"missing attack template: {ATTACK_TEMPLATE}")
    ensure(WORKBENCH_TEMPLATE.exists(), f"missing workbench template: {WORKBENCH_TEMPLATE}")

    reset_workbench(ctx, True)

    reporter = ReportLog()
    create_default_report_sections(ctx, reporter)
    actions = create_actions(ctx, reporter)

    run_crud_checks(ctx, actions)
    run_reset_checks(ctx, actions)
    run_workbench_script_check(ctx, actions)
    run_attack_and_simulation_checks(ctx, actions, reporter)
    run_reporting_checks(ctx, actions, reporter)

    print("Smoke test completed successfully.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="*", type=Path, help="the config files to use")
    ap.add_argument(
        "--default-config",
        type=Path,
        default=Path("./config/default.json"),
        help="the default configuration file to use",
    )
    args = ap.parse_args()

    cfg = load_configs(args.config, args.default_config)
    setup_logging(cfg)
    main(cfg)
