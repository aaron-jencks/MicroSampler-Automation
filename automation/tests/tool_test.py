from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import parse_configs
from tools import MissingAttackAssemblyError, create_read_attack_assembly_tool


class AttackAssemblyToolTestCase(unittest.TestCase):
    def test_read_attack_assembly_returns_deployed_assembly(self):
        config = parse_configs([])
        assembly_path = config.harness.deployment_prefix / config.harness.assembly_file
        assembly_path.write_text("helper_start:\n\tret\n")

        read_attack_assembly = create_read_attack_assembly_tool(config)
        result = read_attack_assembly.invoke({})

        self.assertIn(str(assembly_path), result)
        self.assertIn("helper_start", result)

    def test_read_attack_assembly_raises_when_missing(self):
        config = parse_configs([])
        read_attack_assembly = create_read_attack_assembly_tool(config)

        with self.assertRaises(MissingAttackAssemblyError):
            read_attack_assembly.invoke({})


if __name__ == '__main__':
    unittest.main()
