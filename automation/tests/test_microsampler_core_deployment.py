import unittest

from config import parse_configs
from simulation.microsampler.core.qsm import MicroSamplerCoreDeploymentMachine
from simulation.microsampler.core.defs import MicroSamplerRunConfiguration


class MicroSamplerCoreDeploymentTestCase(unittest.TestCase):
    def check_log_data(self, log_data: str):
        self.assertNotIn("No such file or directory", log_data)

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
