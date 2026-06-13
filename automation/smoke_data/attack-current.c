#include "context.h"
#include "error.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#if defined(__x86_64__) || defined(__i386__)
#include <emmintrin.h>
#endif

/*
 * CLFLUSH-based hot-vs-flushed probe control.
 *
 * Class-dependent condition is created only in trial_inner_setup:
 *   - class 0: read the probe footprint once to leave it resident
 *   - class 1: flush each probe cache line, then execute an ordering barrier,
 *              and do not touch the probe again before timing
 *
 * helper_start performs identical timed-region-side work for both classes:
 * multiple fixed passes of read-only accesses over the exact same probe lines.
 */

#define CACHE_LINE_BYTES 64u
#define WORDS_PER_CACHE_LINE (CACHE_LINE_BYTES / sizeof(uint32_t))
#define PROBE_LINES 64u
#define PROBE_WORDS (PROBE_LINES * WORDS_PER_CACHE_LINE)
#define TIMED_PASSES 4u

typedef struct {
    uint32_t *probe_buf;
    size_t probe_words;
    volatile uint32_t sink;
} attack_global_state_t;

static void read_probe_once(volatile uint32_t *sink, const uint32_t *buf, size_t words)
{
    uint32_t acc = *sink;
    for (size_t i = 0; i < words; i += WORDS_PER_CACHE_LINE) {
        acc ^= buf[i];
    }
    *sink = acc;
}

static void read_probe_multipass(volatile uint32_t *sink, const uint32_t *buf, size_t words, size_t passes)
{
    uint32_t acc = *sink;
    for (size_t p = 0; p < passes; p++) {
        for (size_t i = 0; i < words; i += WORDS_PER_CACHE_LINE) {
            acc ^= buf[i] + (uint32_t)p;
        }
    }
    *sink = acc;
}

static void flush_probe_lines(const uint32_t *buf, size_t words)
{
#if defined(__x86_64__) || defined(__i386__)
    for (size_t i = 0; i < words; i += WORDS_PER_CACHE_LINE) {
        _mm_clflush((const void *)&buf[i]);
    }
    /* Ensure all prior flushes complete before timing begins. */
    _mm_mfence();
#else
    (void)buf;
    (void)words;
#endif
}

void global_setup(global_context_t *ctx)
{
    attack_global_state_t *state = (attack_global_state_t *)malloc(sizeof(*state));
    handle_oom_error(state);

    state->probe_words = PROBE_WORDS;
    state->sink = 0;
    state->probe_buf = (uint32_t *)aligned_alloc(CACHE_LINE_BYTES, state->probe_words * sizeof(uint32_t));
    handle_oom_error(state->probe_buf);

    for (size_t i = 0; i < state->probe_words; i++) {
        state->probe_buf[i] = (uint32_t)(0x9E3779B9u ^ (uint32_t)i);
    }

    ctx->state = state;
}

void global_teardown(global_context_t *ctx)
{
    attack_global_state_t *state = (attack_global_state_t *)ctx->state;
    if (state != NULL) {
        free(state->probe_buf);
        free(state);
        ctx->state = NULL;
    }
}

void trial_setup(bench_context_t *ctx)
{
    (void)ctx;
}

void trial_inner_setup(bench_context_t *ctx, trial_context_t *trial_ctx)
{
    attack_global_state_t *state = (attack_global_state_t *)ctx->global_ctx->state;
    if (state == NULL) {
        return;
    }

    /* Harness-controlled class mapping: zero -> hot/resident, non-zero -> flushed. */
    if (*(trial_ctx->data_len) == 0) {
        read_probe_once(&state->sink, state->probe_buf, state->probe_words);
    } else {
        flush_probe_lines(state->probe_buf, state->probe_words);
    }
}

void trial_teardown(bench_context_t *ctx)
{
    (void)ctx;
}

void helper_start(bench_context_t *ctx)
{
    attack_global_state_t *state = (attack_global_state_t *)ctx->global_ctx->state;
    if (state == NULL) {
        return;
    }

    /* Identical timed-region-side reads for both classes. */
    read_probe_multipass(&state->sink, state->probe_buf, state->probe_words, TIMED_PASSES);
}

void helper_stop(bench_context_t *ctx)
{
    (void)ctx;
}
