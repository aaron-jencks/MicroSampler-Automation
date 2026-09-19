#include "context.h"
#include "fileio.h"
#include "skeleton.h"
#include "wrapper.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define GENERATE_RANDOM_KEY (rand())
#define BUFFER_SIZE 1024

void destroy_trial_context(trial_context_t ctx) {
    free(ctx.dest);
    free(ctx.dummy);
    free(ctx.data);
    free(ctx.data_len);
}

#ifndef NO_TIMING
void generate_json_output(global_context_t ctx, uint64_t* durations, uint32_t* keys) {
    printf("{\n\t\"iterations\": %zd,\n\t\"seed\": %u,\n\t\"data\": [", ctx.iterations, ctx.random_seed);
    for(size_t i = 0; i < ctx.iterations; i++) {
        printf("\n\t\t{\n\t\t\t\"iteration\": %zu,\n\t\t\t\"durations\": [", i);
        for(size_t ki = 0; ki < 32; ki++) {
            uint32_t bit = (uint32_t)((keys[i] >> ki) & 0x1);
            printf("\n\t\t\t\t{ \"bit\": %zu, \"class\": %u, \"key\": %u, \"duration\": %lu }", ki, bit, keys[i], durations[i*32+ki]);
            if(ki < 31) printf(",");
        }
        printf("\n\t\t\t]\n\t\t}");
        if(i < ctx.iterations-1) printf(",");
    }
    printf("\n\t]\n}\n");
}
#endif

int main(int argc, char** argv) {
    size_t iterations = 1;
    unsigned int seed = time(NULL);
    if (argc > 1) {
        sscanf(argv[1], "%zu", &iterations);
        if(argc > 2) {
            sscanf(argv[2], "%u", &seed);
        }
    }
    fprintf(stderr, "Running for %zd iterations with seed %u\n", iterations, seed);

    srand(seed);

    size_t total_bit_iterations = iterations * 32;
#ifndef NO_TIMING
    uint64_t* iteration_durations = malloc(sizeof(uint64_t) * total_bit_iterations);
#endif
    uint32_t* iteration_keys = malloc(sizeof(uint32_t) * iterations);

    global_context_t global_context = create_global_context(iterations, seed);
    global_setup(&global_context);

    for(size_t i = 0; i < iterations; i++) {
        iteration_keys[i] = (uint32_t)GENERATE_RANDOM_KEY;
        bench_context_t run_context = create_context(&global_context, i);
        trial_setup(&run_context);
        for(size_t ki = 0; ki < 32; ki++) {
            uint32_t bit = (uint32_t)((iteration_keys[i] >> ki) & 0x1);
            trial_context_t trial_context = create_default_trial_context(
                BUFFER_SIZE
            );
            trial_inner_setup(&run_context, &trial_context);
            helper_start(&run_context);
#ifdef NO_TIMING
            call_uut(bit, trial_context);
#else
            iteration_durations[i*32+ki] = timed_call_uut(bit, trial_context);
#endif
            helper_stop(&run_context);
            destroy_trial_context(trial_context);
        }
        trial_teardown(&run_context);
    }

    global_teardown(&global_context);

#ifndef NO_TIMING
    generate_json_output(global_context, iteration_durations, iteration_keys);
#endif
}