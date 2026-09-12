import logging
from pathlib import Path
import unittest

from config import parse_configs
from simulation.microsampler.core.defs import PCFinderConfig
from simulation.microsampler.deployment.defs import MicroSamplerTCDeploymentState, MicroSamplerTCRunConfiguration
from simulation.microsampler.deployment.qsm import MicroSamplerTCDeploymentMachine
from simulation.microsampler.core.states import MicroSamplerCoreStepState


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


STATE_TIMEOUTS = {
    MicroSamplerTCDeploymentState.MICROSAMPLER_SIMULATION: 60,
    MicroSamplerTCDeploymentState.MICROSAMPLER_PARSE: 60,
    MicroSamplerTCDeploymentState.MICROSAMPLER_STATS: 60,
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

    def test_deploy_attack_fixture_w_custom_testcase(self):
        config = parse_configs([])
        sm = MicroSamplerTCDeploymentMachine.from_config_file(config.microsampler.core_deployment_qsm, ctx=config)
        for state, timeout in STATE_TIMEOUTS.items():
            self.assertIsInstance(sm.state_map[state], MicroSamplerCoreStepState)
            sm.state_map[state].sp_timeout = timeout
        run_config = MicroSamplerTCRunConfiguration(
            suite="custom_testcase_test",
            apps=["blank_stub"],
            pc_config=PCFinderConfig(
                roi_function="test_ccopy_loop",
                uut_function="ccopy",
                warmup=True
            )
        )

        # prepare test site
        log_prefix = config.microsampler.deployment_prefix / "logs" / run_config.design / run_config.suite / "ct_ccopy" / str(run_config.iterations) / "0xaa"
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


if __name__ == '__main__':
    unittest.main()
