#include "context.h"
#include "encryption_util.h"
#include "error.h"

void global_setup(global_context_t* ctx) {
    (void)ctx;
}

void global_teardown(global_context_t* ctx) {
    (void)ctx;
}

void trial_setup(bench_context_t* ctx) {
    (void)ctx;
}

void trial_inner_setup(bench_context_t* ctx, trial_context_t* trial_ctx) {
    (void)ctx;
    /* Amplify cost so timing differences are easier to resolve. */
    /* data_len is interpreted by UUT as byte length. */
    *trial_ctx->data_len = ENCRYPTION_WORD_COUNT * sizeof(uint32_t);

    /* Touch buffers so pages are mapped similarly before timed call. */
    for (size_t i = 0; i < ENCRYPTION_WORD_COUNT; i++) {
        trial_ctx->dest[i] ^= (uint32_t)i;
        trial_ctx->dummy[i] ^= (uint32_t)(i + 1u);
    }
}

void trial_teardown(bench_context_t* ctx) {
    (void)ctx;
}

void helper_start(bench_context_t* ctx) {
    (void)ctx;
}

void helper_stop(bench_context_t* ctx) {
    (void)ctx;
}
