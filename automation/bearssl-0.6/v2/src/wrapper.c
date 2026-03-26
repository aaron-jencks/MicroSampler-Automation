#include "wrapper.h"
#include "timing.h"

#include <stdint.h>
#include <stddef.h>

uint64_t timed_call_br_i31_modpow_v2(
    bench_context_t* ctx,
    uint32_t *x, uint32_t *r,
    const unsigned char *e, size_t elen,
    const uint32_t *m, uint32_t m0i, uint32_t *t1, uint32_t *t2
) {
    uint64_t start, end, duration;
    start = monotonic_ns();
    br_i31_modpow_v2(x, r, e, elen, m, m0i, t1, t2);
    end = monotonic_ns();
    duration = end - start;
    append_new_time(ctx->is_attack ? ctx->attack_time : ctx->baseline_time, duration);
    return duration;
}