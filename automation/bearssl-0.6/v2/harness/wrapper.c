#include "wrapper.h"
#include "timing.h"
#include "utils.h"
#include "inner.h"

uint64_t timed_call_br_i31_modpow_v2(
    trial_context_t ctx
) {
    uint64_t start, end, duration;
    start = monotonic_ns();
    br_i31_modpow_v2(ctx.x, ctx.r, ctx.e, ctx.elen, ctx.m, ctx.m0i, ctx.t1, ctx.t2);
    end = monotonic_ns();
    return end - start;
}