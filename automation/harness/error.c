#include "error.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

void handle_oom_error(const void* const ptr) {
    if(!ptr) {
        fprintf(stderr, "memory allocation failed!\n");
        exit(1);
    }
}

void generic_error(const char* const fmt, int return_code, ...) {
    va_list args;
    va_start(args, return_code);
    vfprintf(stderr, fmt, args);
    va_end(args);
    exit(return_code);
}