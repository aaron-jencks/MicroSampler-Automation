#ifndef CONTEXT_H
#define CONTEXT_H

#include <stdbool.h>
#include <stddef.h>

#include "timing.h"


typedef struct {
    uint32_t * const x;
    uint32_t * const r;
    unsigned char * const e; 
    size_t elen;
    uint32_t * const m; 
    uint32_t m0i; 
    uint32_t * const t1; 
    uint32_t * const t2;
} trial_context_t;

typedef struct {
    const int class;
    const size_t iterations;
    void* state;
} global_context_t;

typedef struct {
    const global_context_t* const global_ctx;
    const size_t iteration;
    void* state;
} bench_context_t;

global_context_t create_global_context(const int class, const size_t iterations);
bench_context_t create_context(global_context_t* global_ctx, const size_t iteration);

#endif