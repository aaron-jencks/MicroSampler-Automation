#ifndef TIMING_H
#define TIMING_H

#include <stdint.h>
#include <stddef.h>

uint64_t monotonic_ns(void);

typedef struct {
    double sum;
    size_t count;
} timer_aggregation_t;

timer_aggregation_t* create_timer();

void append_new_time(timer_aggregation_t* t, uint64_t ns);
void reset_times(timer_aggregation_t* t);
double get_average_time(timer_aggregation_t* t);

#endif