import logging
import os
from pathlib import Path
import shutil
import subprocess as sp
import tempfile
import unittest
from contextlib import nullcontext

from config import parse_configs
from simulation.microsampler.core.qsm import MicroSamplerCoreDeploymentMachine
from simulation.microsampler.core.defs import MicroSamplerRunConfiguration, MicroSamplerCoreDeploymentState, \
    PCFinderConfig
from simulation.microsampler.core.states import MicroSamplerCoreStepState


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROVEN_PK_COMMIT = "1a52fa44aba49307137ea2ad5263613da33a877b"
PROVEN_GCC_VERSION = "15.3.0"
PK_MATRIX_ROOT = PROJECT_ROOT / "automation" / "crosscompiler-experiment" / "pk-compatibility"
PROVEN_PK = PK_MATRIX_ROOT / "builds" / "pk" / PROVEN_PK_COMMIT / f"gcc-{PROVEN_GCC_VERSION}" / "pk"
PROVEN_GCC_BIN = (
    PROJECT_ROOT / "automation" / "crosscompiler-experiment" / "toolchains"
    / "gcc-15.3.0-rv64gc_zifencei-lp64d" / "bin"
)
PROVEN_GCC = PROVEN_GCC_BIN / "riscv64-unknown-elf-gcc"
PROVEN_OBJDUMP = PROVEN_GCC_BIN / "riscv64-unknown-elf-objdump"
MICROSAMPLER_TESTS = PROJECT_ROOT / "apps" / "bearssl-0.6" / "microsampler_tests"
V2_TIMEOUT_ENV = "MICROSAMPLER_V2_TIMEOUT_SECONDS"


STATE_TIMEOUTS = {
    MicroSamplerCoreDeploymentState.SIMULATION: 1800,
    MicroSamplerCoreDeploymentState.PARSE: 1800,
    MicroSamplerCoreDeploymentState.STATS: 1800,
}


class MicroSamplerCoreDeploymentTestCase(unittest.TestCase):
    def check_log_data(self, log_data: str):
        self.assertNotIn("No such file or directory", log_data)
        self.assertNotIn("ModuleNotFoundError", log_data)
        self.assertNotIn("Traceback (most recent call last):", log_data)

    def check_stats_log_data(self, log_data: str):
        self.check_log_data(log_data)
        self.assertNotIn("findfont: Generic family 'sans-serif' not found because", log_data)
        self.assertNotIn("<FunctionalUnits.", log_data)

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
            self.assertIsInstance(sm.state_map[state], MicroSamplerCoreStepState)
            sm.state_map[state].sp_timeout = timeout

        # Little bit of finagling to get everything to work
        config.microsampler.pc_finder.obj_file = Path("../apps/microbench/ct_ccopy/0xaa/ct_ccopy.dump")
        run_config = MicroSamplerRunConfiguration(
            keys=["0xaa"]
        )

        # prepare test site
        log_prefix = config.microsampler.deployment_prefix / "logs" / run_config.design / config.microsampler.suite / config.microsampler.app / str(run_config.iterations) / "0xaa"
        output_log_files = [
            "out-all-asm.log.gz",
            "uarch.pickle",
            "parser.log",
            "sets.pickle",
            f"stats-{run_config.phi}_{run_config.alpha}.log"
        ]
        for fname in output_log_files:
            log_path = log_prefix / fname
            if log_path.exists():
                log_path.unlink()

        self.assertIsNone(sm.loop_w_config(run_config))

        # check log data
        self.assertEqual(log_prefix, sm.context.log_prefix)
        self.assertTrue(log_prefix.exists())

        for fname in output_log_files:
            self.assertTrue((log_prefix / fname).exists(), f"expected log file {fname} not found")

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
        self.check_stats_log_data(stats_log_data)

    def test_deploy_attack_fixture_with_pk(self):
        """Run v2 using the PK x GCC pair proven by the BOOM matrix.

        The matrix success used PK 1a52fa44... with GCC 15.3.0.  Build v2 in a
        private temporary directory so this test neither relies on nor rewrites
        the ordinary prebuilt BearSSL artifacts.
        """
        for artifact in (PROVEN_PK, PROVEN_GCC, PROVEN_OBJDUMP):
            if not artifact.is_file():
                self.skipTest(
                    "The proven PK x GCC 15.3.0 artifacts are unavailable; "
                    "run the PK compatibility matrix on this host first: "
                    f"{artifact}"
                )

        config = parse_configs([])
        config.microsampler.working_directory = PROJECT_ROOT
        config.microsampler.pk_path = PROVEN_PK
        config.microsampler.boom_seed = 1
        config.microsampler.suite = "bearssl_synthetic"
        config.microsampler.app = "v2"
        config.microsampler.pc_finder.roi_function = "br_i31_modpow_v2"
        config.microsampler.pc_finder.uut_function = "br_ccopy_v2"
        config.microsampler.pc_finder.warmup = False

        with tempfile.TemporaryDirectory(prefix="microsampler-v2-gcc15-") as directory:
            debug_root = PROJECT_ROOT / "debug-v2-gcc15"

            if debug_root.exists():
                shutil.rmtree(debug_root)

            debug_root.mkdir(parents=True)

            print(f"DEBUG DIRECTORY: {debug_root}", flush=True)

        with nullcontext(str(debug_root)) as directory:
            temporary_root = Path(directory)
            v2 = temporary_root / "v2"
            
            build = sp.run(
                [
                    "make", "-C", str(MICROSAMPLER_TESTS),
                    f"BDIR={temporary_root}",
                    f"CC={PROVEN_GCC}",
                    f"OBJDUMP={PROVEN_OBJDUMP}",
                    str(v2),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                build.returncode, 0,
                f"Could not build v2 with proven GCC {PROVEN_GCC_VERSION}:\n"
                f"stdout:\n{build.stdout}\nstderr:\n{build.stderr}",
            )
            self.assertTrue(v2.is_file())
            self.assertTrue((temporary_root / "v2.dump").is_file())

            config.microsampler.deployment_prefix = temporary_root / "deployment"
            config.microsampler.pc_finder.obj_file = temporary_root / "v2.dump"
            sm = MicroSamplerCoreDeploymentMachine.from_config_file(
                config.microsampler.core_deployment_qsm, ctx=config
            )
            for state, timeout in STATE_TIMEOUTS.items():
                self.assertIsInstance(sm.state_map[state], MicroSamplerCoreStepState)
                sm.state_map[state].sp_timeout = timeout

            # The proven stub run took about 13 minutes; retain the matrix's
            # 30-minute limit instead of the former 10-minute test limit. A
            # longer deliberate experiment can override this at invocation
            # time, without changing this test's ordinary default.
            timeout_text = os.environ.get(V2_TIMEOUT_ENV, "1800")
            try:
                simulation_timeout = int(timeout_text)
            except ValueError:
                self.fail(f"{V2_TIMEOUT_ENV} must be a positive integer, got {timeout_text!r}")
            self.assertGreater(simulation_timeout, 0, f"{V2_TIMEOUT_ENV} must be positive")
            sm.state_map[MicroSamplerCoreDeploymentState.SIMULATION].sp_timeout = simulation_timeout

            run_config = MicroSamplerRunConfiguration(
                keys=["0xaa"],
                executable=v2,
                executable_args=[
                    (PROJECT_ROOT / "scripts" / "keys" / "0xaa.key").read_text(),
                    "100",
                ],
            )

            log_prefix = config.microsampler.deployment_prefix / "logs" / run_config.design / config.microsampler.suite / config.microsampler.app / str(run_config.iterations) / "0xaa"
            output_log_files = [
                "out-all-asm.log.gz",
                "uarch.pickle",
                "parser.log",
                "sets.pickle",
                f"stats-{run_config.phi}_{run_config.alpha}.log"
            ]

            self.assertIsNone(sm.loop_w_config(run_config))

            self.assertEqual(log_prefix, sm.context.log_prefix)
            self.assertTrue(log_prefix.exists())

            for fname in output_log_files:
                self.assertTrue((log_prefix / fname).exists(), f"expected log file {fname} not found")

            simulation_log_data = (log_prefix / "launch_simulation.log").read_text()
            parse_log_data = (log_prefix / "launch_parse.log").read_text()
            stats_log_data = (log_prefix / "launch_stats.log").read_text()

            print("simulation log:")
            print(simulation_log_data)
            print("parse log:")
            print(parse_log_data)
            print("stats log:")
            print(stats_log_data)

            self.check_log_data(simulation_log_data)
            self.check_log_data(parse_log_data)
            self.check_stats_log_data(stats_log_data)


if __name__ == '__main__':
    unittest.main()
