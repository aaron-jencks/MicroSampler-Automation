from pathlib import Path
import shutil
from typing import Dict
import unittest

from cascade_config import CascadeConfig

from interpreter.common import PythonInterpreter


def load_configs() -> Dict:
    conf = CascadeConfig()
    conf.add_json(Path("config/default.json"))
    conf.add_json(Path("config/ccopy_v2.json"))
    return conf.parse()


class InterpreterTestCase(unittest.TestCase):
    def test_interpreter(self):
        config = load_configs()
        venv_path = Path(config["interpreter"]["venv_path"])
        if venv_path.exists():
            print("removing old venv instance")
            shutil.rmtree(venv_path)
        self.assertFalse(venv_path.exists(), "venv should not exist prior to first interpreter run")
        interpreter = PythonInterpreter(config)
        interpreter.run("import numpy, pandas, sklearn, scipy;print('hello world')")
        self.assertTrue(venv_path.exists(), "venv should exist after first interpreter call")
        print("cleaning up")
        shutil.rmtree(venv_path)


if __name__ == '__main__':
    unittest.main()
