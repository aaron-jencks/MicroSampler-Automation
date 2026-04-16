#ifndef CONTEXT_H
#define CONTEXT_H

/*
This file contains the definitions for the contexts that will be passed to the client during execution.
trial_context_t contains the definition for the parameters that will be passed to the UUT, this will be pre-populated by the harness, but can be modified by the client later
global_context_t contains the definition of the global state, this can be modified by global_setup and global_teardown, but not in the trial_ functions.
bench_context_t contains the definition of the trial/iteration specific state, it also has a read-only copy of the global state, this cannot be modified, but the state member can be modified by the trial_ functions.
*/

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


typedef struct {
    uint32_t * const dest;      // The real output buffer
    uint32_t * const dummy;     // The dummy output buffer
    uint32_t * const data;      // The data to copy
    size_t * const data_len;    // The number of bytes in the data buffer
    const uint32_t * const key; // The key to use
} trial_context_t;

typedef struct {
    const size_t iterations;        // the number of iterations the UUT will be run for
    const unsigned int random_seed  // the random seed used for generating the keys
    void* state;                    // for use by the client, allows storing global state, can be read, but not modified during the test iterations
} global_context_t;

typedef struct {
    const global_context_t* const global_ctx;   // read-only global state may have user-defined state in the state variable
    const size_t iteration;                     // defines which iteration this is
    const uint32_t key;                         // the full key being used for this iteration
    void* state;                                // modifiable bench state that can be modified during the iteration
} bench_context_t;


/// @brief Used by the harness to initialize the parameters to be passed to the UUT.
/// @param key The key to be used in the trial
/// @param data_size The number of elements that the array should contain
/// @return Returns an initialized struct that can be passed to the trial_ functions and the UUT.
trial_context_t create_default_trial_context(const uint32_t key, size_t data_size);

/// @brief Used by the harness to reset things like buffer state before each UUT call.
/// @param ctx The trial context to reset
void reset_trial_context(trial_context_t* const ctx);


/// @brief Used by the harness to initialize the global context
/// @param iterations the number of iterations to run the UUT for
/// @param random_seed the random seed used for key generation
/// @return a global context ready to be used by the client
global_context_t create_global_context(const size_t iterations, const unsigned int random_seed);

/// @brief creates an iteration context for the client
/// @param global_ctx a read-only copy of the global context
/// @param key the random key being used for this iteration
/// @param iteration the current iteration
/// @return an iteration context ready to be used by the client
bench_context_t create_context(global_context_t* global_ctx, const uint32_t key, const size_t iteration);

#endif