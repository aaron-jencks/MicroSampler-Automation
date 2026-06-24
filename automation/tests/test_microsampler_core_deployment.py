import unittest

from config import parse_configs
from simulation.microsampler.core.qsm import MicroSamplerCoreDeploymentMachine
from simulation.microsampler.core.defs import MicroSamplerRunConfiguration


class MicroSamplerCoreDeploymentTestCase(unittest.TestCase):
    def test_deploy_attack_fixture(self):
        config = parse_configs([])
        sm = MicroSamplerCoreDeploymentMachine.from_config_file(config.microsampler.core_deployment_qsm, ctx=config)
        self.assertIsNone(sm.loop_w_config(MicroSamplerRunConfiguration(
            suite="bearssl_synthetic",
            apps=["v1"],
            keys=["0xaa"]
        )))


if __name__ == '__main__':
    unittest.main()
