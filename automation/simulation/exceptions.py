from typing import Any


class SubprocessError(Exception):
    def __init__(self, code: int, stdout: str, stderr: str, *args: Any) -> None:
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
