#include "context.h"
#include "utils.h"
#include "inner.h"

#include <stdlib.h>

trial_context_t create_default_trial_context(char* key, size_t iters) {
    trial_context_t ctx = {
        .x = (uint32_t*)malloc(sizeof(uint32_t) * 35),
        .r = (uint32_t*)malloc(sizeof(uint32_t) * 35),
        .e = (unsigned char*)malloc(sizeof(unsigned char) * 128),
        .elen = (iters + 7) >> 3,
        .m = (uint32_t*)malloc(sizeof(uint32_t) * 35),
        .t1 = (uint32_t*)malloc(sizeof(uint32_t) * 35),
        .t2 = (uint32_t*)malloc(sizeof(uint32_t) * 35)
    };

    for(int i = 0; i < 35; i++) {
        int temp = i + 1;
        ctx.x[i] = temp;
        ctx.m[i] = temp;
    }

    ctx.m0i = br_i31_ninv31(ctx.m[1]);
    str2hex(key, ctx.e, 128);

    return ctx;
}

global_context_t create_global_context(const int class, const size_t iterations, const char* const * const keys, const size_t key_count) {
    global_context_t result = {
        .class = class,
        .iterations = iterations,
        .keys = keys,
        .key_count = key_count,
        .state = NULL
    };
    return result;
}

bench_context_t create_context(global_context_t* global_ctx, const size_t iteration) {
    bench_context_t result = {
        .global_ctx = global_ctx,
        .iteration = iteration,
        .state = NULL
    };
    return result;
}