from pathlib import Path

from config import BaseConfig


def get_report_directory(ctx: BaseConfig) -> Path:
    dpath = Path(ctx["final_report"]["prefix"]) / ctx["final_report"]["run_name"]
    dpath.mkdir(parents=True, exist_ok=True)
    return dpath
