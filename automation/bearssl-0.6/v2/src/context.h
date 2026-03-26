#ifndef CONTEXT_H
#define CONTEXT_H

#include <stdbool.h>
#include <stddef.h>

#include "timing.h"

typedef struct {
    bool is_attack;
    timer_aggregation_t* baseline_time;
    timer_aggregation_t* attack_time;
} bench_context_t;

#endif