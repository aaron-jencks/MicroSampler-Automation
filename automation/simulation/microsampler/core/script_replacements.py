from dataclasses import dataclass
from enum import StrEnum
import logging
from pathlib import Path
import subprocess as sp
from typing import Type

from config import BaseConfig
from .exceptions import SubprocessError


logger = logging.getLogger(__name__)


@dataclass
class SubprocessArguments:
    log_prefix: Path
    log_name: str
    err: Type[SubprocessError]
    next_state: StrEnum
    executable: Path
    key: str
    suite: str
    app: str
    phi: float
    alpha: float
    window: int
    design: str
    iterations: int


def load_key_value(ctx: BaseConfig, cfg: SubprocessArguments) -> str:
    with open(ctx.microsampler.working_directory / "scripts" / "keys" / f"{cfg.key}.key") as f:
        return f.read()


def do_simulation(ctx: BaseConfig, cfg: SubprocessArguments):
    logger.info(f"Running simulation script replacement")
    get_path = lambda p: str(p.resolve().absolute())
    sim_root = ctx.microsampler.working_directory
    pk = get_path(ctx.microsampler.riscv_root / "riscv64-unknown-elf" / "bin" / "pk")
    keyval = load_key_value(ctx, cfg)
    simulator = get_path(sim_root / "BOOM_simulator")
    executable_path = get_path(cfg.executable)
    stdout_path = get_path(cfg.log_prefix / "stdout.txt")
    temp_log_path = cfg.log_prefix / "out-all.log"
    stderr_path = get_path(temp_log_path)
    logger.info(f"command: {simulator} +verbose {pk} {executable_path} {keyval} > {stdout_path} 2> {stderr_path}")
    stdout_fd = open(stdout_path, "w+")
    stderr_fd = open(stderr_path, "w+")
    try:
        sp.run([
                "time", simulator,
                "+verbose", pk,
                executable_path, keyval
            ],
            stdout=stdout_fd, stderr=stderr_fd,
            shell=False, check=False
        )
    finally:
        stdout_fd.close()
        stderr_fd.close()
    logger.info("Running spike-dasm on output log...")
    output_log = stderr_path
    output_log_fd = open(output_log, "r")
    stdout_path = get_path(cfg.log_prefix / "out-all-asm.log")
    stdout_fd = open(stdout_path, "w+")
    try:
        sp.run([
                "spike-dasm"
            ],
            stdin=output_log_fd,
            stdout=stdout_fd,
            shell=False, check=False
        )
    finally:
        output_log_fd.close()
        stdout_fd.close()
    logger.info("Compressing output log into gzip format...")
    sp.run([
            "gzip", "-f", stdout_path,
        ],
        shell=False, check=False
    )
    logger.info("Cleaning up.....")
    temp_log_path.unlink()
    logger.info("done.")