#define _POSIX_C_SOURCE 200809L

#include "timing.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <time.h>

uint64_t monotonic_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

timer_aggregation_t* create_timer() {
    timer_aggregation_t* t = calloc(1, sizeof(timer_aggregation_t));
    return t;
}

void append_new_time(timer_aggregation_t* t, uint64_t ns) {
    t->sum += (double)ns;
    t->count++;
}
void reset_times(timer_aggregation_t* t) {
    t->sum = 0.0;
    t->count = 0;
}
double get_average_time(timer_aggregation_t* t) {
    return t->sum / (double)t->count;
}