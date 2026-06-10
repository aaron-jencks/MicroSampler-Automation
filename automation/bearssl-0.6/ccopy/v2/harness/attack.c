#include "context.h"
#include "error.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

/*
 * Hypothesis implementation:
 * - Allocate one modest, aligned probe buffer once in global_setup.
 * - Pre-touch it once in setup to reduce first-use effects.
 * - In trial_inner_setup, map class 1 to a deterministic cache walk:
 *   touch one byte per cache line across the probe buffer.
 * - Class 0 performs no probe walk.
 * - No per-trial allocation/reallocation; teardown frees global state.
 */

typedef struct {
    uint8_t *raw_alloc;     /* original pointer for free() */
    uint8_t *probe_aligned; /* cache-line aligned probe base */
    size_t probe_size;      /* bytes */
    size_t line_size;       /* assumed cache line bytes */
    volatile uint8_t sink;  /* prevents optimizing away touches */
} attack_state_t;

static attack_state_t *get_state(const global_context_t *gctx) {
    return (attack_state_t *)gctx->state;
}

void global_setup(global_context_t *ctx) {
    if (!ctx) {
        return;
    }

    attack_state_t *st = (attack_state_t *)calloc(1, sizeof(*st));
    handle_oom_error(st);

    st->line_size = 64u;
    st->probe_size = 8u * 1024u; /* modest fixed size: 8 KiB */

    /*
     * Over-allocate to enforce alignment manually without relying on
     * non-portable aligned alloc APIs.
     */
    size_t alloc_size = st->probe_size + st->line_size;
    st->raw_alloc = (uint8_t *)malloc(alloc_size);
    handle_oom_error(st->raw_alloc);

    uintptr_t p = (uintptr_t)st->raw_alloc;
    uintptr_t aligned = (p + (uintptr_t)(st->line_size - 1u)) & ~(uintptr_t)(st->line_size - 1u);
    st->probe_aligned = (uint8_t *)aligned;

    /* Pre-touch for both classes (done once globally, class-independent). */
    for (size_t i = 0; i < st->probe_size; i += st->line_size) {
        st->probe_aligned[i] = (uint8_t)(i & 0xFFu);
    }

    st->sink = 0;
    ctx->state = st;
}

void global_teardown(global_context_t *ctx) {
    if (!ctx) {
        return;
    }

    attack_state_t *st = get_state(ctx);
    if (st) {
        free(st->raw_alloc);
        st->raw_alloc = NULL;
        st->probe_aligned = NULL;
        free(st);
    }
    ctx->state = NULL;
}

void trial_setup(bench_context_t *ctx) {
    (void)ctx;
}

void trial_inner_setup(bench_context_t *ctx, trial_context_t *trial_ctx) {
    (void)ctx;
    if (!trial_ctx || !trial_ctx->dest || !trial_ctx->dummy) {
        return;
    }

    /*
     * Harness class semantics:
     * - class 1 => dest points to real output buffer
     * - class 0 => dest points to dummy buffer
     * Use this to trigger class-dependent pre-timing cache walk.
     */
    if (trial_ctx->dest != trial_ctx->dummy) {
        attack_state_t *st = NULL;
        if (ctx && ctx->global_ctx) {
            st = get_state(ctx->global_ctx);
        }
        if (!st || !st->probe_aligned) {
            return;
        }

        /* Deterministic one-byte-per-cache-line read walk. */
        volatile uint8_t acc = st->sink;
        for (size_t i = 0; i < st->probe_size; i += st->line_size) {
            acc ^= st->probe_aligned[i];
        }
        st->sink = acc;
    }
}

void trial_teardown(bench_context_t *ctx) {
    (void)ctx;
}

void helper_start(bench_context_t *ctx) {
    (void)ctx;
}

void helper_stop(bench_context_t *ctx) {
    (void)ctx;
}
