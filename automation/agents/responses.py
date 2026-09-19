import random as rng
import sys
from typing import List, Optional

from pydantic import Field

from prompting.responses import DryRunnableBaseModel
from simulation.ccopy.struct import RunConfiguration


class Hypothesis(DryRunnableBaseModel):
    hypothesis: str = Field(description="Hypothesis that you would like to evaluate on this run")
    previous_implementation_bugs: List[str] = Field(description="List of bugs that you would like to fix on this run")
    run_configuration: RunConfiguration = Field(description="The run settings")

    @classmethod
    def from_dry_run(cls):
        return cls(
            hypothesis="Dry run, no hypothesis supplied",
            previous_implementation_bugs=[],
            run_configuration=RunConfiguration(
                global_iterations=2,  # Just to catch any transient errors between loops
                inner_iterations=2,  # Just to catch any transient errors between loops
                run_name="Dry run",
                random_seed=rng.randint(0, sys.maxsize),
            )
        )


class Implementation(DryRunnableBaseModel):
    attack_code: str = Field(description="The attack source code to use for the deployment")
    changes: Optional[List[str]] = Field(None, description="The changes that you made from the last deployment")

    @classmethod
    def from_dry_run(cls):
        return cls(
            attack_code="""
#include "context.h"
#include "encryption_util.h"
#include "error.h"

void global_setup(global_context_t* ctx) {
    (void)ctx;
}

void global_teardown(global_context_t* ctx) {
    (void)ctx;
}

void trial_setup(bench_context_t* ctx) {
    (void)ctx;
}

void trial_inner_setup(bench_context_t* ctx, trial_context_t* trial_ctx) {
    (void)ctx;
    (void)trial_ctx;
}

void trial_teardown(bench_context_t* ctx) {
    (void)ctx;
}

void helper_start(bench_context_t* ctx) {
    (void)ctx;
}

void helper_stop(bench_context_t* ctx) {
    (void)ctx;
}
            """,
            changes=[],
        )


class Summarization(DryRunnableBaseModel):
    description: str = Field(description="Summarization of the statistics from the simulation output")
    suggestion: str = Field(description="Suggestion for what to test for in the next run")
    failure_reason: str = Field(description="Reason why the run did not output a significant leakage")
    bugs: List[str] = Field(description="List of bugs that need to be fixed for the next run")

    @classmethod
    def from_dry_run(cls):
        return cls(
            description="Dry run, no summarization",
            suggestion="",
            failure_reason="",
            bugs=[],
        )
