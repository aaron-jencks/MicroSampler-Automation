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
    (void)trial_ctx;
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
