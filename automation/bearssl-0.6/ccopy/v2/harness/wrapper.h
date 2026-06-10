#ifndef WRAPPER_H
#define WRAPPER_H

#include <stdint.h>

#include "context.h"

uint64_t timed_call_uut(
    uint32_t key,
    trial_context_t ctx
);

#endif