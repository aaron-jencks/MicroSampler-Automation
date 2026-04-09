#include "context.h"
#include "encryption_util.h"
#include "error.h"
#include "utils.h"
#include "inner.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

trial_context_t create_default_trial_context(char* key, size_t iters) {
    if(key == NULL) generic_error("key for trial was empty!\n", 1);

    size_t word_count = ENCRYPTION_WORD_COUNT;
    size_t mlen_bytes = word_count * sizeof(uint32_t);
    size_t elen = (iters + 7) >> 3;

    trial_context_t ctx = {
        .x = (uint32_t*)malloc(mlen_bytes),
        .r = (uint32_t*)malloc(mlen_bytes),
        .e = (unsigned char*)malloc(sizeof(unsigned char) * elen),
        .elen = elen,
        .m = (uint32_t*)malloc(mlen_bytes),
        .t1 = (uint32_t*)malloc(mlen_bytes),
        .t2 = (uint32_t*)malloc(mlen_bytes)
    };

    handle_oom_error(ctx.x);
    handle_oom_error(ctx.r);
    handle_oom_error(ctx.e);
    handle_oom_error(ctx.m);
    handle_oom_error(ctx.t1);
    handle_oom_error(ctx.t2);

    size_t klen = strlen(key);
    if(klen < (ctx.elen << 1)) generic_error("key length too short for requested bit length (got %d, need %d)\n", 1, klen, ctx.elen);
    if(klen > (ctx.elen << 1)) fprintf(stderr, "key length longer than exponent bits, the key will be truncated (got %d, expected %d)\n", klen, ctx.elen);

    fill_words_deterministically(ctx.x, word_count, 0x11111111u);
    fill_words_deterministically(ctx.r, word_count, 0x22222222u);
    fill_words_deterministically(ctx.m, word_count, 0x33333333u);
    fill_words_deterministically(ctx.t1, word_count, 0x44444444u);
    fill_words_deterministically(ctx.t2, word_count, 0x55555555u);

    ctx.m[0] = (uint32_t)ENCRYPTION_MODULUS_BITS;

    ctx.m0i = br_i31_ninv31(ctx.m[1]);

    memset(ctx.e, 0, ctx.elen);
    str2hex(key, ctx.e, 128);

    return ctx;
}

global_context_t create_global_context(const int class, const size_t iterations) {
    global_context_t result = {
        .class = class,
        .iterations = iterations,
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