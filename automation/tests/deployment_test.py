import json
from pathlib import Path
from typing import Dict, List
import unittest

from cascade_config import CascadeConfig

from simulation.struct import RunConfiguration
from simulation.utils import write_attack_source, run_simulation


ATTACK_STUB = Path("smoke_data/attack-stub.c")


def load_configs() -> Dict:
    conf = CascadeConfig()
    conf.add_json(Path("config/default.json"))
    conf.add_json(Path("config/ccopy_v2.json"))
    return conf.parse()


class BuildingDeploymentCase(unittest.TestCase):
    def test_deployment(self):
        config = load_configs()
        with open(ATTACK_STUB) as f:
            attack_source = f.read()
        write_attack_source(config, attack_source)
        run_simulation(config, RunConfiguration(
            1, 1, "unit-test", 42
        ))



if __name__ == '__main__':
    unittest.main()
