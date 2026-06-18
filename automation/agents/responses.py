from typing import List, Optional

from pydantic import BaseModel, Field

from simulation.ccopy.struct import RunConfiguration


class Hypothesis(BaseModel):
    hypothesis: str = Field(description="Hypothesis that you would like to evaluate on this run")
    previous_implementation_bugs: List[str] = Field(description="List of bugs that you would like to fix on this run")
    run_configuration: RunConfiguration = Field(description="The run settings")


class Implementation(BaseModel):
    attack_code: str = Field(description="The attack source code to use for the deployment")
    changes: Optional[List[str]] = Field(None, description="The changes that you made from the last deployment")


class Summarization(BaseModel):
    description: str = Field(description="Summarization of the statistics from the simulation output")
    suggestion: str = Field(description="Suggestion for what to test for in the next run")
    failure_reason: str = Field(description="Reason why the run did not output a significant leakage")
    bugs: List[str] = Field(description="List of bugs that need to be fixed for the next run")
