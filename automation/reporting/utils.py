from pathlib import Path
from typing import Dict


def get_report_directory(ctx: Dict) -> Path:
    dpath = Path(ctx["final_report"]["prefix"]) / ctx["final_report"]["run_name"]
    dpath.mkdir(parents=True, exist_ok=True)
    return dpath
