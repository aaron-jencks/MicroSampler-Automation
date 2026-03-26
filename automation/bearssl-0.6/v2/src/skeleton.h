#ifndef SKELETON_H
#define SKELETON_H

#include "context.h"

void bench_init(bench_context_t* ctx);
void bench_target(bench_context_t* ctx);
void bench_cleanup(bench_context_t* ctx);

#endif