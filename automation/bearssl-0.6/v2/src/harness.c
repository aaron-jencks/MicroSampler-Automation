#include "context.h"
#include "skeleton.h"
#include "timing.h"

#include <stdbool.h>
#include <stdio.h>

void main(int argc, char** argv) {
    size_t iterations = 1000;
    if (argc > 0) {
        sscanf(argv[0], "%zd", &iterations);
    }
    printf("Running for %zd iterations\n", iterations);
    bench_context_t run_context = {
        false,
        create_timer(),
        create_timer()
    };
    for(size_t i = 0; i < iterations; i++) {
        reset_times(&run_context);
        bench_init(&run_context);
        bench_target(&run_context);
        bench_cleanup(&run_context);
        run_context.is_attack = !run_context.is_attack;
    }
}