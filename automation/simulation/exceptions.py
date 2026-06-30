from typing import Any, Optional


class SubprocessError(Exception):
    def __init__(self, code: int, stdout: Optional[str] = None, stderr: Optional[str] = None, *args: Any):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        if len(args) > 0:
            super().__init__(*args)
        else:
            super().__init__(f"subprocess failed with code {self.code}")

    def format_error(self) -> str:
        return f"""Return code: {self.code}
        Stdout:
        {self.stdout}

        Stderr:
        {self.stderr}
        """
