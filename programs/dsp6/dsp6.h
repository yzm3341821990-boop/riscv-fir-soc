#ifndef DSP6_H
#define DSP6_H
#include "cpu5.h"
#define DSP6_FIR ((volatile uint32_t *)0x40003000u)
#define DSP6_MARKER (*(volatile uint32_t *)0x40004000u)
#define DSP6_BARRIER() __asm__ volatile ("" ::: "memory")
static inline int dsp6_load_coefficients(const int32_t *h) {
    for(unsigned k=0;k<32;k++) {
        if(h[k]<-32768 || h[k]>32767) return 1;
        DSP6_FIR[64+k]=(uint32_t)h[k];
    }
    return 0;
}
static inline int dsp6_fir(const int32_t *src,int32_t *dst,unsigned count) {
    uintptr_t a=(uintptr_t)src,b=(uintptr_t)dst;
    if(count<1 || count>4096 || (a&3) || (b&3) || a<0x10000000u || b<0x10000000u ||
       a>0x10008000u-4*count || b>0x10008000u-4*count ||
       (a<b+4*count && b<a+4*count)) return 2;
    DSP6_FIR[0]=2;
    DSP6_FIR[2]=(uint32_t)(a-0x10000000u);
    DSP6_FIR[3]=(uint32_t)(b-0x10000000u);
    DSP6_FIR[4]=count;
    DSP6_BARRIER();DSP6_FIR[0]=1;
    unsigned status=0;
    for(unsigned polls=0;polls<count*64u+256u;polls++) {
        status=DSP6_FIR[1];
        if(!(status&1u)) break;
    }
    DSP6_BARRIER();
    return status!=2u || DSP6_FIR[6]!=count || DSP6_FIR[7]!=0u;
}
static inline void dsp6_begin(unsigned path) { DSP6_BARRIER();DSP6_MARKER=path;DSP6_BARRIER(); }
static inline void dsp6_end(void) { DSP6_BARRIER();DSP6_MARKER=0;DSP6_BARRIER(); }
#endif
