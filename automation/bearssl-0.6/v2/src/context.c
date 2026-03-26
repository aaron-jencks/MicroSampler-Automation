#include "context.h"

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