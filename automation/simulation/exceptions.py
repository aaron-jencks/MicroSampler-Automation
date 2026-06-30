from pathlib import Path
from typing import Any, Optional, Union


PROC_OUTPUT = Optional[Union[str, Path]]


class SubprocessError(Exception):
    def __init__(self, code: int, stdout: PROC_OUTPUT = None, stderr: PROC_OUTPUT = None, *args: Any):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        if len(args) > 0:
            super().__init__(*args)
        else:
            super().__init__(f"subprocess failed with code {self.code}")

    def format_error(self) -> str:
        stdout = self.stdout
        if isinstance(self.stdout, Path):
            stdout = self.stdout.read_text()
        stderr = self.stderr
        if isinstance(self.stderr, Path):
            stderr = self.stderr.read_text()
        return f"""Return code: {self.code}
        Stdout:
        {stdout}

        Stderr:
        {stderr}
        """
