#ifndef SKELETON_H
#define SKELETON_H

#include "context.h"

/*
This file defines the interface that must be implemented by the client.

None of these functions must be implemented, they can be as simple as an empty body.

The general flow for these functions is as follows:

```
global_context_t global_context = create_global_context(iterations);
global_setup(&global_context);

for(size_t i = 0; i < iterations; i++) {
    iteration_keys[i] = (uint32_t)GENERATE_RANDOM_KEY;
    bench_context_t run_context = create_context(&global_context, iteration_keys[i], i);
    trial_setup(&run_context);
    for(size_t ki = 0; ki < 32; ki++) {
        uint32_t bit = (uint32_t)((iteration_keys[i] >> ki) & 0x1);
        trial_context_t trial_context = create_default_trial_context(
            bit,
            BUFFER_SIZE
        );
        trial_inner_setup(&run_context, &trial_context);
        helper_start(&run_context);
        iteration_durations[i] = timed_call_br_ccopy_v2(trial_context);
        helper_stop(&run_context);
        destroy_trial_context(trial_context);
    }
    trial_teardown(&run_context);
}

global_teardown(&global_context);
```

global_setup and global_teardown are used if iterations > 1, it allows the client to initialize the system state, start processes, threads, whatever they need. If they need to pass information between setup and teardown, store it in the state member of the ctx parameter.
trial_setup and trial_inner_setup allow the client to initialize the system state further with finer control. This state is setup and torn down every iteration. trial_setup is called before the trial context is generated and trial_inner_setup is called for each bit of the key after the context is generated.
    ^ The client should not spawn processes or threads here, instead this should be used to setup state, any processes or threads should be performed in helper_start and helper_stop.
      Do not free the arrays inside of the trial_context_t, you can modify
helper_start and helper_stop can be used to initialize the system, spawn processes, etc...
*/

void global_setup(global_context_t* ctx);
void global_teardown(global_context_t* ctx);
void trial_setup(bench_context_t* ctx);
void trial_inner_setup(bench_context_t* ctx, trial_context_t* trial_ctx);
void trial_teardown(bench_context_t* ctx);
void helper_start(bench_context_t* ctx);
void helper_stop(bench_context_t* ctx);

#endif