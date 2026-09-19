#ifndef FILEIO_H
#define FILEIO_H

#include <stddef.h>

char** read_key_file(char* fname, size_t* output_count, size_t max_length);

#endif