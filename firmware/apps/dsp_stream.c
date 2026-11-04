#include "dsp6.h"
#include "dsp_signal.h"
static int32_t samples[256],software[256],hardware[256],history[31],window[96];
static int32_t quantize(int64_t v) {
    int64_t m=v<0?-v:v;
    int32_t q=(int32_t)((m+16384)>>15);
    if(v<0) q=-q;
    return q>32767?32767:q<-32768?-32768:q;
}
__attribute__((noinline)) static void software_fir(void) {
    for(unsigned n=0;n<256;n++) {
        int64_t sum=0;
        for(unsigned k=0;k<32 && k<=n;k++) {
            int32_t product=samples[n-k]*dsp_coefficients[k];
            sum+=(int64_t)product;
        }
        software[n]=quantize(sum);
    }
}
int main(void) {
    unsigned n=job.input_count?(unsigned)job.input[0]:4096u;
    if(n<1 || n>262144) return 10;
    uint32_t swsum=0,coldsum=0,ressum=0,errors=0,blocks=0;
    for(unsigned offset=0;offset<n;) {
        unsigned take=n-offset<225?n-offset:225;
        for(unsigned i=0;i<31;i++) samples[i]=history[i];
        for(unsigned i=0;i<225;i++) samples[31+i]=i<take?dsp_signal[(offset+i)%48]:0;
        dsp6_begin(1);software_fir();dsp6_end();
        dsp6_begin(2);
        int e=dsp6_load_coefficients(dsp_coefficients);
        if(!e) e=dsp6_fir(samples,hardware,256);
        dsp6_end();
        if(e) return 20+e;
        for(unsigned i=0;i<256;i++) if(software[i]!=hardware[i]) errors++;
        for(unsigned i=0;i<take;i++) coldsum=coldsum*16777619u+(uint32_t)hardware[31+i];
        dsp6_begin(3);e=dsp6_fir(samples,hardware,256);dsp6_end();
        if(e) return 30+e;
        for(unsigned i=0;i<256;i++) if(software[i]!=hardware[i]) errors++;
        for(unsigned i=0;i<take;i++) {
            swsum=swsum*16777619u+(uint32_t)software[31+i];
            ressum=ressum*16777619u+(uint32_t)hardware[31+i];
            window[(offset+i)%96]=hardware[31+i];
        }
        for(unsigned i=0;i<31;i++) history[i]=samples[take+i];
        offset+=take;blocks++;
    }
    unsigned k=n<96?n:96;
    job.output[0]=(int32_t)n;job.output[1]=(int32_t)blocks;
    job.output[2]=(int32_t)swsum;job.output[3]=(int32_t)coldsum;job.output[4]=(int32_t)ressum;job.output[5]=(int32_t)errors;
    job.output[6]=(int32_t)k;
    for(unsigned i=0;i<k;i++) job.output[7+i]=window[(n-k+i)%96];
    job.output_count=7+k;
    cpu5_puts("DSP6 CPU + four-lane FIR; checked samples=");cpu5_print_u32(n);cpu5_putc('\n');
    return errors?40:0;
}
