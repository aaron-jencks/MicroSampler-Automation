#ifndef ERROR_H
#define ERROR_H

void handle_oom_error(const void* const ptr);
void generic_error(const char* const fmt, int return_code, ...);

#endif