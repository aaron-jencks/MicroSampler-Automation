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


def setup_temporary_file_logger(cfg: SubprocessArguments) -> logging.Handler:
    file_handler = logging.FileHandler(cfg.log_prefix / cfg.log_name)
    file_handler.setFormatter(logger.handlers[0].formatter)

    logger.addHandler(file_handler)

    return file_handler


def cleanup_temporary_file_logger(handler: logging.Handler):
    logger.removeHandler(handler)
    handler.close()


def do_simulation(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    sim_handler = setup_temporary_file_logger(cfg)
    try:
        logger.info(f"Running simulation script replacement")

        logger.info("Setting up directory structure...")
        cfg.log_prefix.mkdir(parents=True, exist_ok=True)

        sim_root = ctx.microsampler.working_directory
        pk = get_path(ctx.microsampler.riscv_root / "riscv64-unknown-elf" / "bin" / "pk")
        simulator = get_path(sim_root / "BOOM_simulator")
        if not cfg.executable.exists():
            raise FileNotFoundError(f"Executable not found: {cfg.executable}")
        executable_path = get_path(cfg.executable)
        stdout_path = cfg.log_prefix / "stdout.txt"
        temp_log_path = cfg.log_prefix / "out-all.log"
        stderr_path = temp_log_path

        sim_args = [
            "time", simulator, "+verbose"
        ]
        if cfg.suite != "microbench":
            sim_args.append(pk)
        sim_args.append(executable_path)
        sim_args.extend(cfg.executable_args)

        logger.info(f"command: {' '.join(sim_args)} > {stdout_path} 2> {stderr_path}")
        sim_ret = run_default_subprocess(ctx, sim_args,
            stdout=stdout_path, stderr=stderr_path,
            timeout=cfg.timeout,
        )
        if sim_ret.returncode != 0:
            logger.warning("Simulation process had non-zero return")
            return sim_ret
        logger.info("Running spike-dasm on output log...")
        output_log = stderr_path
        stdout_path = cfg.log_prefix / "out-all-asm.log"
        spike_ret = run_default_subprocess(ctx, [
                "spike-dasm"
            ],
            stdin=output_log,
            stdout=stdout_path,
            timeout=cfg.timeout
        )
        if spike_ret.returncode != 0:
            logger.warning("spike-dasm process had non-zero return")
            return spike_ret
        logger.info("Compressing output log into gzip format...")
        gzip_ret = run_default_subprocess(ctx, [
                "gzip", "-f", get_path(stdout_path),
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
    finally:
        cleanup_temporary_file_logger(sim_handler)


def do_parse(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    parse_handler = setup_temporary_file_logger(cfg)
    try:
        logger.info("Parsing micro-arch log, collecting state samples...")
        sim_root = ctx.microsampler.working_directory
        script_path = get_path(sim_root / "scripts" / "parse_trace.py")
        asm_log_path = get_path(cfg.log_prefix / "out-all-asm.log.gz")
        uarch_path = get_path(cfg.log_prefix / "uarch.pickle")
        log_path = cfg.log_prefix / "parser.log"
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
            stdout=log_path, stderr=sp.STDOUT,
            timeout=cfg.timeout
        )
    finally:
        cleanup_temporary_file_logger(parse_handler)


def do_stats(ctx: BaseConfig, cfg: SubprocessArguments) -> Optional[sp.CompletedProcess]:
    stats_handler = setup_temporary_file_logger(cfg)
    try:
        logger.info("Running state analysis...")
        sim_root = ctx.microsampler.working_directory
        script_path = get_path(sim_root / "scripts" / "stats.py")
        key_path = get_path(ctx.microsampler.working_directory / "scripts" / "keys" / f"{cfg.key}.key")
        uarch_path = get_path(cfg.log_prefix / "uarch.pickle")
        sets_path = get_path(cfg.log_prefix / "sets.pickle")
        log_path = cfg.log_prefix / f"stats-{cfg.phi}_{cfg.alpha}.log"
        stats_ret = run_default_subprocess(ctx, [
                "time", "python", script_path,
                uarch_path, key_path, sets_path,
                get_path(cfg.log_prefix),
                str(cfg.phi), str(cfg.alpha), str(cfg.window), str(cfg.iterations),
            ],
            stdout=log_path, stderr=sp.STDOUT,
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
            stdout=log_path, stderr=sp.STDOUT,
            timeout=cfg.timeout
        )
    finally:
        cleanup_temporary_file_logger(stats_handler)
