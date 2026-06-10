#include "wrapper.h"
#include "timing.h"
#include "utils.h"
#include "inner.h"

uint64_t timed_call_uut(
    uint32_t key,
    trial_context_t ctx
) {
    size_t i;
    uint64_t start, end, duration;
    start = monotonic_ns();
    br_ccopy(key, ctx.dest, ctx.data, *ctx.data_len);
    end = monotonic_ns();
    return end - start;
}