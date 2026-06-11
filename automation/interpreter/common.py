from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess as sp
from typing import Optional

from config import BaseConfig

logger = logging.getLogger(__file__)


@dataclass
class InterpreterResult:
    exit_code: int = 0
    timedout: bool = False
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class PythonInterpreter:
    def __init__(self, ctx: BaseConfig):
        self.ctx = ctx

    def _get_venv_path(self) -> Path:
        return Path(self.ctx["interpreter"]["venv_path"])

    def _get_python_path(self) -> Path:
        return self._get_venv_path() / "bin" / "python"

    def _check_for_venv(self):
        logger.info("checking venv status")
        p = self._get_venv_path()
        if not p.is_dir() or not p.exists():
            logger.info(f"setting up venv in {p.resolve()}")
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                sp.run(["python", "-m", "venv", str(p.resolve())], capture_output=True, check=True)
            except sp.CalledProcessError as e:
                raise RuntimeError(f"failed to create venv:\n{e}")
            pip_path = p / "bin" / "pip"
            requirements_path = Path(self.ctx["interpreter"]["requirements_path"])
            try:
                sp.run([str(pip_path.resolve()), "install", "-r", str(requirements_path.resolve())], capture_output=True, check=True)
            except sp.CalledProcessError as e:
                raise RuntimeError(f"failed to install packages:\n{e}")
            if not self._get_python_path().exists():
                raise RuntimeError("python didn't exist after setting up venv")
        else:
            logger.info(f"using venv in {self._get_python_path()}")

    def run(self, code: str) -> InterpreterResult:
        logger.info("running interpreter")
        self._check_for_venv()
        logger.info("running code")
        python_path = self._get_venv_path() / "bin" / "python"
        try:
            result = sp.run(
                [str(python_path.resolve()), "-"],
                input=code,
                text=True,
                capture_output=True, timeout=self.ctx["interpreter"]["timeout"]
            )
            logger.info(f"interpreter finished with exit code: {result.returncode}")
            return InterpreterResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr
            )
        except sp.TimeoutExpired:
            logger.info("interpreter timed out")
            return InterpreterResult(
                timedout=True,
            )
