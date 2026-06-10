from datetime import datetime, timezone
from typing import Any, Optional

from agents.defs import LoopState


class ReportEvent:
    def __init__(self, iteration: int, state: LoopState, kind: str, payload: Optional[Any]):
        self.iteration = iteration
        self.state = state
        self.kind = kind
        self.timestamp = datetime.now(tz=timezone.utc)
        self.payload = payload