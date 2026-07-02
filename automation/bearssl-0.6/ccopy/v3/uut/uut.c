#include "uut.h"
#include "utils.h"
#include "inner.h"

void uut(
    uint32_t key,
    trial_context_t ctx
) {
    br_ccopy(key, ctx.dest, ctx.data, *ctx.data_len);
}