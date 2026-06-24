from typing import Optional, Any

from qstate import QSM

from .defs import MicroSamplerRunConfiguration


class MicroSamplerCoreDeploymentMachine(QSM):
    def loop_w_config(self, run_config: MicroSamplerRunConfiguration, flush: bool = True) -> Optional[Any]:
        self.context.context.run_config = run_config
        super().loop(flush)
