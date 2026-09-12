from typing import Optional, Any

from qstate import QSM

from .defs import MicroSamplerTCRunConfiguration


class MicroSamplerTCDeploymentMachine(QSM):
    def loop_w_config(self, run_config: MicroSamplerTCRunConfiguration, flush: bool = True) -> Optional[Any]:
        self.context.run_config = run_config
        return super().loop(flush)
