#include "encryption_util.h"

void fill_words_deterministically(uint32_t* const dest, size_t n, uint8_t seed) {
    uint32_t v = seed;
    for (size_t i = 0; i < n; i++) {
        v = v * 1664525u + 1013904223u;  // simple LCG
        dest[i] = v;
    }
}