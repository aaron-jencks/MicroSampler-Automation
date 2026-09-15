from config import BaseConfig
from .core.defs import MicroSamplerRunConfiguration


def derive_run_configuration(cfg: BaseConfig, base_config: MicroSamplerRunConfiguration) -> MicroSamplerRunConfiguration:
    base_config.suite = cfg.microsampler.suite
    base_config.apps = [cfg.microsampler.app]
    base_config.pc_config.roi_function = cfg.microsampler.pc_finder.roi_function
    base_config.pc_config.uut_function = cfg.microsampler.pc_finder.uut_function
    base_config.pc_config.warmup = cfg.microsampler.pc_finder.warmup
    if cfg.microsampler.pc_finder.obj_file is not None:
        base_config.pc_config.obj_file = cfg.microsampler.pc_finder.obj_file
    else:
        base_config.pc_config.obj_file = cfg.harness.deployment_prefix / cfg.harness.assembly_file
    return base_config