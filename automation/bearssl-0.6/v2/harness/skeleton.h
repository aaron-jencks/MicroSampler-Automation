#ifndef SKELETON_H
#define SKELETON_H

#include "context.h"

/*
This file defines the interface that must be implemented by the client.

None of these functions must be implemented, they can be as simple as an empty body.

The general flow for these functions is as follows:

```
global_context_t global_context = create_global_context(class, iterations);

global_setup(&global_context);

for(size_t i = 0; i < iterations; i++) {
    iteration_keys[i] = malloc(sizeof(char) * MAX_KEY_LEN);
    bench_context_t run_context = create_context(&global_context, i);

    trial_pre_setup(&run_context);

    trial_generate_key(&run_context, iteration_keys[i], MAX_KEY_LEN);
    
    truncate key if necessary
    generate default trial context with pre-popualted data

    trial_post_setup(&run_context, &trial_context);

    helper_start(&run_context);

    iteration_durations[i] = UUT(trial_context);

    helper_stop(&run_context);

    trial_teardown(&run_context);

    destroy_trial_context(trial_context);
}

global_teardown(&global_context);
```

global_setup and global_teardown are used if iterations > 1, it allows the client to initialize the system state, start processes, threads, whatever they need. If they need to pass information between setup and teardown, store it in the state member of the ctx parameter.
trial_pre_setup and trial_post_setup allow the client to initialize the system state further with finer control. This state is setup and torn down every iteration. pre_setup is called before the trial context is generated and post_setup is called after.
    ^ The client should not spawn processes or threads here, instead this should be used to setup state, any processes or threads should be performed in helper_start and helper_stop.
      Do not free the arrays inside of the trial_context_t, you can modify
trial_generate_key is responsible for generating the key string to be passed into the UUT, it should be zero-terminated, if not it will be truncated. Do not free the buffer. The key can be at most max_len characters.
helper_start and helper_stop can be used to initialize the system, spawn processes, etc...
*/

void global_setup(global_context_t* ctx);
void global_teardown(global_context_t* ctx);
void trial_pre_setup(bench_context_t* ctx);
void trial_generate_key(bench_context_t* ctx, char* const buffer, size_t max_len);
void trial_post_setup(bench_context_t* ctx, trial_context_t* trial_ctx);
void trial_teardown(bench_context_t* ctx);
void helper_start(bench_context_t* ctx);
void helper_stop(bench_context_t* ctx);

#endif