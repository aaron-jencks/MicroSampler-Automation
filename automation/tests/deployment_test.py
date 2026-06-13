from pathlib import Path
import unittest

from config import parse_configs
from simulation.api.ccopy import CCopyDeploymentController
from simulation.struct import RunConfiguration
from tools import create_read_attack_assembly_tool


ATTACK_SOURCE = Path("smoke_data/attack-current.c")


class BuildingDeploymentTestCase(unittest.TestCase):
    def deploy_attack_fixture(self):
        config = parse_configs([Path("config/ccopy_v3.json")])
        attack_source = ATTACK_SOURCE.read_text()

        controller = CCopyDeploymentController(config)
        controller.deploy_test_case(attack_source, config=RunConfiguration(
            1, 1, "unit-test", 42
        ))
        return config

    def test_deployment_copies_attack_assembly(self):
        config = self.deploy_attack_fixture()
        assembly_path = config.harness.deployment_prefix / config.harness.assembly_file
        self.assertTrue(assembly_path.exists())
        assembly = assembly_path.read_text(errors="replace")
        self.assertIn("helper_start", assembly)
        self.assertIn("trial_inner_setup", assembly)

    def test_smoke_attack_compiles_and_assembly_tool_reads_output(self):
        config = self.deploy_attack_fixture()
        read_attack_assembly = create_read_attack_assembly_tool(config)
        assembly = read_attack_assembly.invoke({})

        self.assertIn(str(config.harness.deployment_prefix / config.harness.assembly_file), assembly)
        self.assertIn("helper_start", assembly)
        self.assertIn("trial_inner_setup", assembly)
        self.assertIn("clflush", assembly)
        self.assertIn("mfence", assembly)


if __name__ == '__main__':
    unittest.main()
