#ifndef WRAPPER_H
#define WRAPPER_H

#include <stdint.h>
#include <stddef.h>

#include "skeleton.h"

uint64_t timed_call_br_i31_modpow_v2(
    bench_context_t* ctx,
    uint32_t *x, uint32_t *r,
    const unsigned char *e, size_t elen,
    const uint32_t *m, uint32_t m0i, uint32_t *t1, uint32_t *t2
);

#endif