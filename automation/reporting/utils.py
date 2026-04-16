from pathlib import Path
from typing import Dict


def get_report_directory(ctx: Dict):
    dpath = Path(ctx["general_prefix"]) / ctx["final_report"]["prefix"]
    dpath.mkdir(parents=True, exist_ok=True)
    return dpath