#include "uut.h"
#include "utils.h"
#include "inner.h"

void uut(
    uint32_t key,
    trial_context_t ctx
) {
    br_ccopy_v2(key, ctx.dest, ctx.dummy, ctx.data, *ctx.data_len);
}