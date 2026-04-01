import logging
import os
from pathlib import Path
import shutil
import subprocess as sp
from typing import Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


def get_workbench_path(ctx: Dict) -> Path:
    return Path(ctx["workbench"]["prefix"])


def reset_workbench(ctx: Dict, data: bool = False):
    logger.info("resetting/creating workbench")
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        prefix.mkdir(parents=True)

    data_prefix = prefix / ctx["workbench"]["data_directory"]
    if data_prefix.exists() and data:
        shutil.rmtree(data_prefix)
    if not data_prefix.exists():
        data_prefix.mkdir(parents=True)

    # Nuke the workbench
    for item in prefix.iterdir():
        if item == ctx["workbench"]["data_directory"]:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    logger.info("importing over source trees")
    source_prefix = prefix / ctx["workbench"]["source"]["prefix"]
    source_prefix.mkdir(parents=True)
    for key in ctx["workbench"]["source"]["contents"]:
        key_prefix = source_prefix / key
        source_tree = Path(ctx["workbench"]["source"]["contents"][key])
        logger.info(f"importing {key}: {source_tree} -> {key_prefix}")
        if not source_tree.exists():
            raise FileNotFoundError(source_tree)
        shutil.copytree(source_tree, key_prefix, copy_function=shutil.copy)

    script_path = prefix / ctx["workbench"]["script"]
    script_path.touch()


def create_workbench_file(ctx: Dict, fname: str, content: str):
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        reset_workbench(ctx)
    file_path = prefix / fname
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def read_workbench_file(ctx: Dict, fname: str) -> str:
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        reset_workbench(ctx)
    file_path = prefix / fname
    return file_path.read_text()


def delete_workbench_file(ctx: Dict, fname: str):
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        reset_workbench(ctx)
    file_path = prefix / fname
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    file_path.unlink()


def list_workbench_files(ctx: Dict) -> List[str]:
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        reset_workbench(ctx)
    files = []
    for dirpath, dirnames, filenames in os.walk(prefix):
        for filename in filenames:
            files.append(str(Path(dirpath) / filename))
    return files


def run_workbench(ctx: Dict, args: List[str]) -> Tuple[Optional[sp.CompletedProcess[bytes]], bool]:
    prefix = get_workbench_path(ctx)
    if not prefix.exists():
        reset_workbench(ctx)
    script_path = prefix / ctx["workbench"]["script"]
    if not script_path.exists():
        raise FileNotFoundError(script_path)
    response = sp.run(
        ["bash", str(script_path), *args],
        cwd=Path(ctx['workbench']['workbench']).absolute(),
        capture_output=True,
        timeout=300
    )
    return response, False