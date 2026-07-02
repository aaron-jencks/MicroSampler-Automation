#include "wrapper.h"
#include "timing.h"
#include "utils.h"
#include "uut.h"
#include "inner.h"

#ifdef NO_TIMING
void call_uut(
    uint32_t key,
    trial_context_t ctx
) {
    uut(key, ctx);
}
#else
uint64_t timed_call_uut(
    uint32_t key,
    trial_context_t ctx
) {
    uint64_t start, end, duration;
    start = monotonic_ns();
    uut(key, ctx);
    end = monotonic_ns();
    return end - start;
}
#endif