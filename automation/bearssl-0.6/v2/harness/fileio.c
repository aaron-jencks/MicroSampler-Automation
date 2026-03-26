#include "fileio.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#define INITIAL_BUFFER_SIZE 10

char** read_key_file(char* fname, size_t* output_count, size_t max_length) {
    FILE* fp = fopen(fname, "r");
    char** output_buffers = (char**)malloc(sizeof(char*) * INITIAL_BUFFER_SIZE);
    size_t output_capacity = INITIAL_BUFFER_SIZE;
    *output_count = 0;
    while(true) {
        char* buff = (char*)malloc(sizeof(char) * max_length);
        if(fgets(buff, max_length+1, fp)) {
            free(buff);
            break;
        }
        if(*output_count >= output_capacity) {
            output_capacity <<= 1;
            output_buffers = realloc(output_buffers, sizeof(char*) * output_capacity);
        }
        output_buffers[*output_count++] = buff;
    }
    fclose(fp);
    return output_buffers;
}