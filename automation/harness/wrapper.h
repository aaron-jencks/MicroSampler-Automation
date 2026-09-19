#ifndef WRAPPER_H
#define WRAPPER_H

#include <stdint.h>

#include "context.h"

#ifdef NO_TIMING
void call_uut(
    uint32_t key,
    trial_context_t ctx
);
#else
uint64_t timed_call_uut(
    uint32_t key,
    trial_context_t ctx
);
#endif

#endif