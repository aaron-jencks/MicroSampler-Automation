from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import parse_configs
from interpreter.common import PythonInterpreter


class InterpreterTestCase(unittest.TestCase):
    def test_interpreter(self):
        config = parse_configs([Path("config/ccopy_v3.json")])
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            requirements_path = tmp_path / "requirements.txt"
            requirements_path.write_text("")
            config.interpreter.venv_path = tmp_path / "venv"
            config.interpreter.requirements_path = requirements_path

            interpreter = PythonInterpreter(config)
            result = interpreter.run("print('hello world')")

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.stdout, "hello world\n")
            self.assertTrue(config.interpreter.venv_path.exists())


if __name__ == '__main__':
    unittest.main()
