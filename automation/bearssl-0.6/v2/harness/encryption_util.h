#ifndef ENCRYPTION_UTIL_H
#define ENCRYPTION_UTIL_H

#include <stddef.h>
#include <stdint.h>

#define ENCRYPTION_MODULUS_BITS 1024
#define ENCRYPTION_WORD_COUNT ((ENCRYPTION_MODULUS_BITS + 63) >> 5)

void fill_words_deterministically(uint32_t* const dest, size_t n, uint8_t seed);

#endif