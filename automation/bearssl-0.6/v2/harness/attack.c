#include "skeleton.h"

#include <stdint.h>
#include <stddef.h>
#include <string.h>

void global_setup(global_context_t* ctx) {
    (void)ctx;
}

void global_teardown(global_context_t* ctx) {
    (void)ctx;
}

void trial_pre_setup(bench_context_t* ctx) {
    (void)ctx;
}

void trial_generate_key(bench_context_t* ctx, char* const buffer, size_t max_len) {
    (void)ctx;
    if (max_len == 0) {
        return;
    }
    buffer[0] = '\0';
}

void trial_post_setup(bench_context_t* ctx, trial_context_t* trial_ctx) {
    // Keep modulus/x defaults, only control exponent pattern per class.
    // class 0: all exponent bits 0
    // class 1: all exponent bits 1
    memset(trial_ctx->e, (ctx->global_ctx->class == 0) ? 0x00 : 0xFF, 128);

    // Ensure full length is used consistently.
    trial_ctx->elen = 128;
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
