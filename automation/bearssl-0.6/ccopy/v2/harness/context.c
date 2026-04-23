#include "context.h"
#include "encryption_util.h"
#include "error.h"
#include "utils.h"
#include "inner.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

trial_context_t create_default_trial_context(const uint32_t key, size_t data_size) {
    size_t buffer_byte_size = data_size * sizeof(uint32_t);
    uint32_t* key_copy = (uint32_t*)malloc(sizeof(uint32_t));
    handle_oom_error(key_copy);
    *key_copy = key;
    trial_context_t ctx = {
        .dest = (uint32_t*)calloc(data_size, sizeof(uint32_t)),
        .dummy = (uint32_t*)calloc(data_size, sizeof(uint32_t)),
        .data = (uint32_t*)calloc(data_size, sizeof(uint32_t)),
        .data_len = (size_t*)malloc(sizeof(size_t)),
        .key = key_copy,
    };
    handle_oom_error(ctx.dest);
    handle_oom_error(ctx.dummy);
    handle_oom_error(ctx.data);
    fill_words_deterministically(ctx.data, data_size, 0x11111111u);
    *ctx.data_len = buffer_byte_size;
    return ctx;
}

void reset_trial_context(trial_context_t* const ctx) {
    size_t byte_count = *ctx->data_len * sizeof(uint32_t);
    memset(ctx->dest, 0, *ctx->data_len);
    memset(ctx->dummy, 0, *ctx->data_len);
    memset(ctx->data, 0, *ctx->data_len);
    fill_words_deterministically(ctx->data, *ctx->data_len, 0x11111111u);
}

global_context_t create_global_context(const size_t iterations, const unsigned int random_seed) {
    global_context_t result = {
        .iterations = iterations,
        .random_seed = random_seed,
        .state = NULL
    };
    return result;
}

bench_context_t create_context(global_context_t* global_ctx, const uint32_t key, const size_t iteration) {
    bench_context_t result = {
        .global_ctx = global_ctx,
        .iteration = iteration,
        .key = key,
        .state = NULL
    };
    return result;
}