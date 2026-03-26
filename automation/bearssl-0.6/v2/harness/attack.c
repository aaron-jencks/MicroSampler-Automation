#include "skeleton.h"

void global_setup(global_context_t* ctx) {}
void global_teardown(global_context_t* ctx) {}
void trial_pre_setup(bench_context_t* ctx) {}
void trial_generate_key(bench_context_t* ctx, char* const buffer, size_t max_len) {}
void trial_post_setup(bench_context_t* ctx, trial_context_t* trial_ctx) {}
void trial_teardown(bench_context_t* ctx) {}
void helper_start(bench_context_t* ctx) {}
void helper_stop(bench_context_t* ctx) {}

