from pathlib import Path
import shutil
import subprocess as sp
import tempfile
import unittest

from config import parse_configs
from simulation.microsampler.core.qsm import MicroSamplerCoreDeploymentMachine
from simulation.microsampler.core.defs import MicroSamplerRunConfiguration


class MicroSamplerCoreDeploymentTestCase(unittest.TestCase):
    def check_log_data(self, log_data: str):
        self.assertNotIn("No such file or directory", log_data)
        self.assertNotIn("ModuleNotFoundError", log_data)

    def test_cross_compiler_exists(self):
        self.assertIsNotNone(shutil.which("riscv64-unknown-elf-gcc"), "a riscv64-unknown-elf-gcc cross-compiler is required for microsampler deployment")
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

    def test_deploy_attack_fixture(self):
        config = parse_configs([])
        sm = MicroSamplerCoreDeploymentMachine.from_config_file(config.microsampler.core_deployment_qsm, ctx=config)
        run_config = MicroSamplerRunConfiguration(
            suite="bearssl_synthetic",
            apps=["v1"],
            keys=["0xaa"]
        )
        self.assertIsNone(sm.loop_w_config(run_config))

        # check log data
        log_prefix = config.microsampler.deployment_prefix / "logs" / run_config.design / "v1" / str(run_config.iterations) / "0xaa"
        self.assertEqual(log_prefix, sm.context.log_prefix)

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
