#include "context.h"
#include "skeleton.h"
#include "wrapper.h"

#include "utils.h"
#include "inner.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#define CALL_ITERS 100
#define MAX_KEY_LEN 1024

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

void destroy_trial_context(trial_context_t ctx) {
    free(ctx.x);
    free(ctx.r);
    free(ctx.e);
    free(ctx.m);
    free(ctx.t1);
    free(ctx.t2);
}

void generate_json_output(global_context_t ctx, uint64_t* durations, char** keys) {
    printf("{\n\t\"class\": %d,\n\t\"iterations\": %zd,\n\t\"durations\": [", ctx.class, ctx.iterations);
    for(size_t i = 0; i < ctx.iterations; i++) printf("\n\t\t{\"iteration\": %zu, \"duration\": %ld, \"key\": \"%s\"}", i, durations[i], keys[i]);
    printf("\n\t]\n}\n");
}

int main(int argc, char** argv) {
    size_t iterations = 1;
    int class = 0;
    if (argc > 1) {
        sscanf(argv[1], "%d", &class);
        if(argc > 2) sscanf(argv[2], "%zu", &iterations);
    }
    uint64_t* iteration_durations = malloc(sizeof(uint64_t) * iterations);
    char** iteration_keys = malloc(sizeof(char*) * iterations);

    fprintf(stderr, "Running class %d for %zd iterations\n", class, iterations);

    global_context_t global_context = create_global_context(class, iterations);
    if(iterations > 1) global_setup(&global_context);

    for(size_t i = 0; i < iterations; i++) {
        iteration_keys[i] = malloc(sizeof(char) * MAX_KEY_LEN);
        bench_context_t run_context = create_context(&global_context, i);
        trial_pre_setup(&run_context);
        trial_generate_key(&run_context, iteration_keys[i], MAX_KEY_LEN);
        if(iteration_keys[i][MAX_KEY_LEN-1] != 0) iteration_keys[i][MAX_KEY_LEN-1] = 0;
        trial_context_t trial_context = create_default_trial_context(iteration_keys[i], CALL_ITERS);
        trial_post_setup(&run_context, &trial_context);
        helper_start(&run_context);
        iteration_durations[i] = timed_call_br_i31_modpow_v2(trial_context);
        helper_stop(&run_context);
        trial_teardown(&run_context);
        destroy_trial_context(trial_context);
    }

    if(iterations > 1) global_teardown(&global_context);

    generate_json_output(global_context, iteration_durations, iteration_keys);
}