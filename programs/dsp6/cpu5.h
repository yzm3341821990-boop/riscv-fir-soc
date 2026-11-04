#ifndef CPU5_H
#define CPU5_H
#include <stdint.h>
typedef struct {
    uint32_t magic, input_count;
    int32_t input[128];
    uint32_t output_count;
    int32_t output[128];
    uint32_t done, status, console_length;
    char console[256];
} cpu5_job;
extern volatile cpu5_job job;
static inline void cpu5_putc(char c) {
    uint32_t n=job.console_length;
    if(n<256) { job.console[n]=c; job.console_length=n+1; }
}
static inline void cpu5_puts(const char *s) { while(*s) cpu5_putc(*s++); }
static inline void cpu5_print_u32(uint32_t v) {
    char digits[10]; unsigned n=0;
    do { digits[n++]=(char)('0'+v%10); v/=10; } while(v);
    while(n) cpu5_putc(digits[--n]);
}
static inline void cpu5_print_i32(int32_t v) {
    if(v<0) { cpu5_putc('-'); cpu5_print_u32(0u-(uint32_t)v); }
    else cpu5_print_u32((uint32_t)v);
}
#endif
