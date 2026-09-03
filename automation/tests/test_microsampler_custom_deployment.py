import gzip
import logging
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from config import parse_configs
from qstate import QSM
from simulation.microsampler.deployment.defs import (
    MicroSamplerTCDeploymentState,
    MicroSamplerTCRunConfiguration,
)


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


ARBITRARY_ATTACK_PROGRAM = """
#include "context.h"

void global_setup(global_context_t *ctx)
{
    (void)ctx;
}

void global_teardown(global_context_t *ctx)
{
    (void)ctx;
}

void trial_setup(bench_context_t *ctx)
{
    (void)ctx;
}

void trial_inner_setup(
    bench_context_t *ctx,
    trial_context_t *trial_ctx
)
{
    (void)ctx;
    (void)trial_ctx;
}

void trial_teardown(bench_context_t *ctx)
{
    (void)ctx;
}

void helper_start(bench_context_t *ctx)
{
    (void)ctx;
}

void helper_stop(bench_context_t *ctx)
{
    (void)ctx;
}
"""


EXPECTED_STATES = {
    MicroSamplerTCDeploymentState.INITIAL,
    MicroSamplerTCDeploymentState.PREPARE,
    MicroSamplerTCDeploymentState.HARNESS_VERIFY,
    MicroSamplerTCDeploymentState.HARNESS_PREPARE,
    MicroSamplerTCDeploymentState.HARNESS_COMPILE,
    MicroSamplerTCDeploymentState.DEPLOYMENT_PREPARE,
    MicroSamplerTCDeploymentState.KEY_PREPARE,
    MicroSamplerTCDeploymentState.MICROSAMPLER_DEPLOYMENT,
    MicroSamplerTCDeploymentState.MICROSAMPLER_SIMULATION,
    MicroSamplerTCDeploymentState.MICROSAMPLER_PARSE,
    MicroSamplerTCDeploymentState.MICROSAMPLER_STATS,
    MicroSamplerTCDeploymentState.DATA_COLLECTION,
    MicroSamplerTCDeploymentState.LOOP_CHECK,
}


class MicroSamplerCustomDeploymentTestCase(unittest.TestCase):
    FIXED_KEY = "0123456789abcdef"

    def check_log_data(self, log_data: str):
        self.assertTrue(
            log_data.strip(),
            "expected a nonempty log",
        )
        self.assertNotIn(
            "No such file or directory",
            log_data,
        )
        self.assertNotIn(
            "ModuleNotFoundError",
            log_data,
        )
        self.assertNotIn(
            "Traceback (most recent call last):",
            log_data,
        )

    @staticmethod
    def fake_simulation(config, arguments):
        """
        Stand-in for the external BOOM simulation.

        The custom QSM still reaches and executes its simulation state,
        but this unit test does not require BOOM_simulator or spike-dasm.
        """
        arguments.log_prefix.mkdir(
            parents=True,
            exist_ok=True,
        )

        simulation_log = (
            arguments.log_prefix
            / "launch_simulation.log"
        )
        simulation_log.write_text(
            "simulation complete\n"
        )

        simulation_trace = (
            arguments.log_prefix
            / "out-all-asm.log.gz"
        )
        with gzip.open(
            simulation_trace,
            mode="wt",
        ) as trace:
            trace.write(
                "Cycle=1 custom test trace\n"
            )

        return None

    @staticmethod
    def fake_parse(config, arguments):
        """
        Stand-in for the external trace parser.
        """
        arguments.log_prefix.mkdir(
            parents=True,
            exist_ok=True,
        )

        parse_log = (
            arguments.log_prefix
            / "launch_parse.log"
        )
        parse_log.write_text(
            "parse complete\n"
        )

        parser_output_log = (
            arguments.log_prefix
            / "parser.log"
        )
        parser_output_log.write_text(
            "parser produced sampled state\n"
        )

        parsed_state = (
            arguments.log_prefix
            / "uarch.pickle"
        )
        parsed_state.write_bytes(
            b"custom-test-uarch-data"
        )

        return None

    @staticmethod
    def fake_stats(config, arguments):
        """
        Stand-in for the external statistics scripts.
        """
        arguments.log_prefix.mkdir(
            parents=True,
            exist_ok=True,
        )

        stats_log = (
            arguments.log_prefix
            / "launch_stats.log"
        )
        stats_log.write_text(
            "stats complete\n"
        )

        stats_output = (
            arguments.log_prefix
            / (
                f"stats-{arguments.phi}_"
                f"{arguments.alpha}.log"
            )
        )
        stats_output.write_text(
            "custom test statistics\n"
        )

        sets_file = (
            arguments.log_prefix
            / "sets.pickle"
        )
        sets_file.write_bytes(
            b"custom-test-set-data"
        )

        return None

    def test_custom_microsampler_deployment(self):
        repository_root = (
            Path(__file__).resolve().parents[2]
        )
        automation_root = (
            repository_root / "automation"
        )

        source_harness_directory = (
            automation_root
            / "bearssl-0.6"
            / "ccopy"
            / "v2"
            / "harness"
        )
        source_uut_directory = (
            automation_root
            / "bearssl-0.6"
            / "ccopy"
            / "v2"
            / "uut"
        )
        bearssl_source_directory = (
            repository_root
            / "apps"
            / "bearssl-0.6"
            / "src"
        )
        bearssl_include_directory = (
            repository_root
            / "apps"
            / "bearssl-0.6"
            / "inc"
        )
        qsm_config_path = (
            automation_root
            / "config"
            / "governor"
            / "microsampler_deployment_custom_qsm.json"
        )

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)

            harness_directory = (
                temp_root / "harness"
            )
            deployment_directory = (
                temp_root / "deployment"
            )
            microsampler_directory = (
                temp_root / "microsampler"
            )
            key_directory = (
                microsampler_directory
                / "scripts"
                / "keys"
            )

            shutil.copytree(
                source_harness_directory,
                harness_directory,
            )

            config = parse_configs([])

            config.harness.prefix = (
                harness_directory
            )
            config.harness.deployment_prefix = (
                deployment_directory
            )
            config.harness.uut.prefix = (
                source_uut_directory
            )
            config.harness.uut.file = "uut.c"
            config.harness.target = "attack.c"
            config.harness.executable = "harness"
            config.harness.assembly_file = "attack.s"

            config.harness.make_defines = [
                "LOCAL=1",
                (
                    "BEARSSL_SRC_ROOT="
                    f"{bearssl_source_directory}"
                ),
                (
                    "BEARSSL_INC_ROOT="
                    f"{bearssl_include_directory}"
                ),
            ]

            config.microsampler.working_directory = (
                microsampler_directory
            )
            config.microsampler.deployment_prefix = (
                microsampler_directory
            )

            key_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            state_machine = QSM.from_config_file(
                qsm_config_path,
                ctx=config,
            )

            configured_states = set(
                state_machine.state_map.keys()
            )

            for expected_state in EXPECTED_STATES:
                self.assertIn(
                    expected_state.value,
                    configured_states,
                    (
                        "custom QSM is missing state "
                        f"{expected_state.value}"
                    ),
                )

            run_config = (
                MicroSamplerTCRunConfiguration(
                    suite="custom",
                    apps=["custom_harness"],
                    iterations=1,
                    global_iterations=1,
                    key_size=len(self.FIXED_KEY),
                    fixed_key=self.FIXED_KEY,
                )
            )

            state_machine.context.implementation = (
                ARBITRARY_ATTACK_PROGRAM
            )
            state_machine.context.run_config = (
                run_config
            )

            with (
                patch(
                    "simulation.microsampler."
                    "core.states.do_simulation",
                    side_effect=self.fake_simulation,
                ),
                patch(
                    "simulation.microsampler."
                    "core.states.do_parse",
                    side_effect=self.fake_parse,
                ),
                patch(
                    "simulation.microsampler."
                    "core.states.do_stats",
                    side_effect=self.fake_stats,
                ),
            ):
                result = state_machine.loop()

            self.assertIsNone(result)

            attack_source = (
                harness_directory / "attack.c"
            )
            built_executable = (
                harness_directory / "harness"
            )
            deployed_executable = (
                deployment_directory / "harness"
            )
            deployed_assembly = (
                deployment_directory / "attack.s"
            )

            self.assertTrue(
                attack_source.exists(),
                "attack source was not written",
            )
            self.assertEqual(
                attack_source.read_text(),
                ARBITRARY_ATTACK_PROGRAM,
            )
            self.assertTrue(
                built_executable.exists(),
                "custom harness was not compiled",
            )
            self.assertTrue(
                deployed_executable.exists(),
                "custom harness was not deployed",
            )
            self.assertTrue(
                deployed_assembly.exists(),
                "attack assembly was not deployed",
            )
            self.assertEqual(
                state_machine.context.run_config.executable,
                deployed_executable,
            )

            key_files = list(
                key_directory.glob("*.key")
            )
            self.assertEqual(
                len(key_files),
                1,
                "expected exactly one generated key file",
            )
            self.assertEqual(
                key_files[0].read_text(),
                self.FIXED_KEY,
            )
            self.assertEqual(
                state_machine.context.current_key_name,
                key_files[0].stem,
            )
            self.assertEqual(
                state_machine.context.run_config.keys,
                [key_files[0].stem],
            )

            self.assertEqual(
                state_machine.context.current_global_iteration,
                1,
            )

            log_prefix = (
                state_machine.context.log_prefix
            )
            self.assertIsNotNone(log_prefix)
            self.assertTrue(log_prefix.exists())

            expected_artifacts = [
                "out-all-asm.log.gz",
                "uarch.pickle",
                "parser.log",
                "sets.pickle",
                (
                    f"stats-{run_config.phi}_"
                    f"{run_config.alpha}.log"
                ),
                "launch_simulation.log",
                "launch_parse.log",
                "launch_stats.log",
            ]

            for artifact_name in expected_artifacts:
                artifact = (
                    log_prefix / artifact_name
                )
                self.assertTrue(
                    artifact.exists(),
                    (
                        "expected artifact not found: "
                        f"{artifact}"
                    ),
                )

            self.check_log_data(
                (
                    log_prefix
                    / "launch_simulation.log"
                ).read_text()
            )
            self.check_log_data(
                (
                    log_prefix
                    / "launch_parse.log"
                ).read_text()
            )
            self.check_log_data(
                (
                    log_prefix
                    / "launch_stats.log"
                ).read_text()
            )

            self.assertEqual(
                len(
                    state_machine.context.collected_data
                ),
                1,
                (
                    "expected one collected result "
                    "for one global iteration"
                ),
            )

            collected_result = (
                state_machine.context.collected_data[0]
            )

            self.assertEqual(
                collected_result.key_name,
                key_files[0].stem,
            )
            self.assertEqual(
                collected_result.key_file,
                key_files[0],
            )
            self.assertEqual(
                collected_result.executable,
                deployed_executable,
            )
            self.assertEqual(
                collected_result.log_prefix,
                log_prefix,
            )


if __name__ == "__main__":
    unittest.main()