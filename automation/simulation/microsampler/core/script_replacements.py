from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess as sp
from typing import List, Optional

from config import BaseConfig
from ..pc_finder import UUTPCAddresses
from tools import get_path, run_default_subprocess


logger = logging.getLogger(__name__)


@dataclass
class SubprocessArguments:
    log_prefix: Path
    log_name: str
    executable: Path
    executable_args: List[str]
    key: str
    suite: str
    app: str
    phi: float
    alpha: float
    window: int
    design: str
    iterations: int
    pc_addresses: UUTPCAddresses
    timeout: Optional[float] = None


def load_key_value(ctx: BaseConfig, key: str) -> str:
    with open(ctx.microsampler.working_directory / "scripts" / "keys" / f"{key}.key") as f:
        return f.read()


def do_simulation(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    logger.info(f"Running simulation script replacement")
    sim_root = ctx.microsampler.working_directory
    pk = get_path(ctx.microsampler.riscv_root / "riscv64-unknown-elf" / "bin" / "pk")
    simulator = get_path(sim_root / "BOOM_simulator")
    executable_path = get_path(cfg.executable)
    stdout_path = get_path(cfg.log_prefix / "stdout.txt")
    temp_log_path = cfg.log_prefix / "out-all.log"
    stderr_path = get_path(temp_log_path)
    logger.info(f"command: {simulator} +verbose {pk} {executable_path} {' '.join(cfg.executable_args)} > {stdout_path} 2> {stderr_path}")
    stdout_fd = open(stdout_path, "w+")
    stderr_fd = open(stderr_path, "w+")
    try:
        sim_ret = run_default_subprocess(ctx, [
                "time", simulator,
                "+verbose", pk,
                executable_path,
                *cfg.executable_args,
            ],
            stdout=stdout_fd, stderr=stderr_fd,
            timeout=cfg.timeout,
        )
        if sim_ret.returncode != 0:
            logger.warning("Simulation process had non-zero return")
            return sim_ret
    finally:
        stdout_fd.close()
        stderr_fd.close()
    logger.info("Running spike-dasm on output log...")
    output_log = stderr_path
    output_log_fd = open(output_log, "r")
    stdout_path = get_path(cfg.log_prefix / "out-all-asm.log")
    stdout_fd = open(stdout_path, "w+")
    try:
        spike_ret = run_default_subprocess(ctx, [
                "spike-dasm"
            ],
            stdin=output_log_fd,
            stdout=stdout_fd,
            timeout=cfg.timeout
        )
        if spike_ret.returncode != 0:
            logger.warning("spike-dasm process had non-zero return")
            return spike_ret
    finally:
        output_log_fd.close()
        stdout_fd.close()
    logger.info("Compressing output log into gzip format...")
    gzip_ret = run_default_subprocess(ctx, [
            "gzip", "-f", stdout_path,
        ],
        timeout=cfg.timeout
    )
    if gzip_ret.returncode != 0:
        logger.warning("gzip process had non-zero return")
        return gzip_ret
    logger.info("Cleaning up.....")
    temp_log_path.unlink()
    logger.info("done.")
    return None


def do_parse(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    logger.info("Parsing micro-arch log, collecting state samples...")
    sim_root = ctx.microsampler.working_directory
    script_path = get_path(sim_root / "scripts" / "parse_trace.py")
    asm_log_path = get_path(cfg.log_prefix / "out-all-asm.log.gz")
    uarch_path = get_path(cfg.log_prefix / "uarch.pickle")
    log_path = cfg.log_prefix / "parser.log"
    log_fd = open(log_path, "w+")
    pc_config = cfg.pc_addresses
    return run_default_subprocess(ctx, [
            "time", "python", script_path,
            asm_log_path, uarch_path,
            f"0x{pc_config.roi_start:010x}",
            f"0x{pc_config.roi_end:010x}",
            f"0x{pc_config.calling_address:010x}",
            f"0x{pc_config.start_address:010x}",
            f"0x{pc_config.return_address:010x}"
        ],
        stdout=log_fd, stderr=sp.STDOUT,
        timeout=cfg.timeout
    )


def do_stats(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    logger.info("Running state analysis...")
    sim_root = ctx.microsampler.working_directory
    script_path = get_path(sim_root / "scripts" / "stats.py")
    key_path = get_path(ctx.microsampler.working_directory / "scripts" / "keys" / f"{cfg.key}.key")
    uarch_path = get_path(cfg.log_prefix / "uarch.pickle")
    sets_path = get_path(cfg.log_prefix / "sets.pickle")
    log_path = cfg.log_prefix / f"stats-{cfg.phi}_{cfg.alpha}.log"
    log_fd = open(log_path, "w+")
    stats_ret = run_default_subprocess(ctx, [
            "time", "python", script_path,
            uarch_path, key_path, sets_path,
            get_path(cfg.log_prefix),
            str(cfg.phi), str(cfg.alpha), str(cfg.window), str(cfg.iterations),
        ],
        stdout=log_fd, stderr=sp.STDOUT,
        timeout=cfg.timeout
    )
    if stats_ret.returncode != 0:
        logger.warning("stats process had non-zero return")
        return stats_ret
    script_path = get_path(sim_root / "scripts" / "miss_stats.py")
    return run_default_subprocess(ctx, [
            "python", script_path,
            cfg.app, cfg.key, cfg.design, cfg.suite, str(cfg.iterations), str(cfg.window)
        ],
        stdout=log_fd, stderr=sp.STDOUT,
        timeout=cfg.timeout
    )
