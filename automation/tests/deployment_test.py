from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import parse_configs
from simulation.api.ccopy import CCopyDeploymentController
from simulation.struct import RunConfiguration


ATTACK_SOURCE = Path("smoke_data/attack-current.c")


class BuildingDeploymentTestCase(unittest.TestCase):
    def test_deployment_copies_attack_assembly(self):
        config = parse_configs([Path("config/ccopy_v3.json")])
        with TemporaryDirectory() as deploy_dir:
            config.harness.deployment_prefix = Path(deploy_dir)
            with open(ATTACK_SOURCE) as f:
                attack_source = f.read()

            controller = CCopyDeploymentController(config)
            controller.deploy_test_case(attack_source, config=RunConfiguration(
                1, 1, "unit-test", 42
            ))

            assembly_path = config.harness.deployment_prefix / config.harness.assembly_file
            self.assertTrue(assembly_path.exists())
            assembly = assembly_path.read_text(errors="replace")
            self.assertIn("helper_start", assembly)
            self.assertIn("trial_inner_setup", assembly)


if __name__ == '__main__':
    unittest.main()
