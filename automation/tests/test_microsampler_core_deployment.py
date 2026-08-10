import logging
from pathlib import Path
import shutil
import subprocess as sp
import tempfile
import unittest

from config import parse_configs
from simulation.microsampler.core.qsm import MicroSamplerCoreDeploymentMachine
from simulation.microsampler.core.defs import MicroSamplerRunConfiguration, MicroSamplerCoreDeploymentState, \
    PCFinderConfig
from simulation.microsampler.core.states import MicroSamplerSubprocessState


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


STATE_TIMEOUTS = {
    MicroSamplerCoreDeploymentState.SIMULATION: 60,
    MicroSamplerCoreDeploymentState.PARSE: 60,
    MicroSamplerCoreDeploymentState.STATS: 60,
}


class MicroSamplerCoreDeploymentTestCase(unittest.TestCase):
    def check_log_data(self, log_data: str):
        self.assertNotIn("No such file or directory", log_data)
        self.assertNotIn("ModuleNotFoundError", log_data)

    def test_cross_compiler_exists(self):
        logger.debug("testing cross-compiler existence")
        self.assertIsNotNone(shutil.which("riscv64-unknown-elf-gcc"), "a riscv64-unknown-elf-gcc cross-compiler is required for microsampler deployment")
        logger.debug("testing cross-compiler version")
        version_output = sp.run(["riscv64-unknown-elf-gcc", "--version"], capture_output=True, text=True)
        self.assertEqual(version_output.returncode, 0, "riscv64-unknown-elf-gcc did not print version successfully")
        version_text = version_output.stdout.splitlines(keepends=False)
        self.assertGreater(len(version_text), 0)
        version_text = version_text[0]
        self.assertEqual(version_text, "riscv64-unknown-elf-gcc (g5115c7e44) 15.2.0", "gcc version expected to be 15.2.0 (g5115c7e44), otherwise expected pc addresses won't match")
        logger.debug("testing cross-compiler features")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "test.c"
            src.write_text("""
        int main(void) {
            __asm__ volatile("fence.i");
            return 0;
        }
        """)

            result = sp.run(
                [
                    "riscv64-unknown-elf-gcc",
                    "-c",
                    str(src),
                    "-o",
                    str(Path(d) / "test.o"),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, "riscv cross-compiler must support the fence instruction")
        self.assertIsNotNone(result.stderr)

    def test_script_replacement_compatibility(self):
        logger.debug("testing spike-dasm existence")
        self.assertIsNotNone(shutil.which("spike-dasm"),"spike-dasm is required for simulation to succeed.")

    def test_prebuilt_code_exists(self):
        output_build_directory = Path("../apps/bearssl-0.6/microsampler_tests/build")
        self.assertTrue(output_build_directory.exists(), "make sure to build the microsampler tests per the readme")
        objects = list(output_build_directory.glob("*.dump"))
        self.assertGreater(len(objects), 0, "make sure to build the microsampler tests per the readme")
        file_names = set(list(map(lambda x: x.stem, objects)))
        expected_files = [
            "v1", "v1_fence", "v1_warmup",
            "v2", "v2_fence", "v2_warmup",
            "v3", "v3_fence", "v3_warmup"
        ]
        for ef in expected_files:
            self.assertIn(ef, file_names, f"expected output program {ef} not found")
        self.assertTrue(Path("../apps/microbench/ct_ccopy/0xaa/ct_ccopy.dump").exists())

    def test_deploy_attack_fixture(self):
        config = parse_configs([])
        sm = MicroSamplerCoreDeploymentMachine.from_config_file(config.microsampler.core_deployment_qsm, ctx=config)
        for state, timeout in STATE_TIMEOUTS.items():
            self.assertIsInstance(sm.state_map[state], MicroSamplerSubprocessState)
            sm.state_map[state].sp_timeout = timeout
        run_config = MicroSamplerRunConfiguration(
            suite="microbench",
            apps=["ct_ccopy"],
            keys=["0xaa"],
            pc_config=PCFinderConfig(
                obj_file=Path("../apps/microbench/ct_ccopy/0xaa/ct_ccopy.dump"),
                roi_function="test_ccopy_loop",
                uut_function="ccopy",
                warmup=True
            )
        )
        self.assertIsNone(sm.loop_w_config(run_config))

        # check log data
        log_prefix = config.microsampler.deployment_prefix / "logs" / run_config.design / run_config.suite / "ct_ccopy" / str(run_config.iterations) / "0xaa"
        self.assertEqual(log_prefix, sm.context.log_prefix)
        self.assertTrue(log_prefix.exists())

        simulation_log = log_prefix / "launch_simulation.log"
        simulation_log_data = simulation_log.read_text()

        parse_log = log_prefix / "launch_parse.log"
        parse_log_data = parse_log.read_text()

        stats_log = log_prefix / "launch_stats.log"
        stats_log_data = stats_log.read_text()

        print("simulation log:")
        print(simulation_log_data)
        print("parse log:")
        print(parse_log_data)
        print("stats log:")
        print(stats_log_data)

        self.check_log_data(simulation_log_data)
        self.check_log_data(parse_log_data)
        self.check_log_data(stats_log_data)


if __name__ == '__main__':
    unittest.main()
