/* Long-block comparison: identical RAM object and compiler for all modes. */
typedef unsigned int u32;
#ifndef SAMPLE_COUNT
#error "SAMPLE_COUNT is required"
#endif
#ifndef BENCH_MODE
#error "BENCH_MODE is required"
#endif
#define FIR ((volatile u32 *)0x40003000u)
#define BARRIER() __asm__ volatile ("" ::: "memory")
struct large_data {
    int samples[SAMPLE_COUNT];
    int coefficients[32];
    int outputs[SAMPLE_COUNT];
    int expected[SAMPLE_COUNT];
    volatile u32 marker,done,errors,polls,hw_cycles,hw_written;
};
struct large_data bench_data;

#if BENCH_MODE == 0
static int quantize(long long accumulator)
{
    long long magnitude=accumulator<0 ? -accumulator:accumulator;
    int value=(int)((magnitude+16384)>>15);
    if(accumulator<0)value=-value;
    if(value>32767)value=32767;
    if(value< -32768)value=-32768;
    return value;
}
__attribute__((noinline)) int run_fir(void)
{
    for(u32 n=0;n<SAMPLE_COUNT;++n){
        long long sum=0;
        for(u32 k=0;k<32 && k<=n;++k){
            int product=bench_data.samples[n-k]*bench_data.coefficients[k];
            sum+=(long long)product;
        }
        bench_data.outputs[n]=quantize(sum);
    }
    return 0;
}
#else
static void load_coefficients(void)
{
    for(u32 k=0;k<32;++k)FIR[64+k]=(u32)bench_data.coefficients[k];
}
__attribute__((noinline)) int run_fir(void)
{
    FIR[0]=2;
#if BENCH_MODE == 1
    load_coefficients();
#endif
    FIR[2]=(u32)bench_data.samples;FIR[3]=(u32)bench_data.outputs;
    FIR[4]=SAMPLE_COUNT;FIR[0]=1;
    u32 status,count=0;
    do{status=FIR[1];++count;}while((status&1u)&&count<SAMPLE_COUNT*64u+256u);
    bench_data.polls=count;
    return status!=2u;
}
#endif
int main(void)
{
#if BENCH_MODE == 2
    load_coefficients();
#endif
    BARRIER();bench_data.marker=1;BARRIER();
    u32 errors=(u32)run_fir();
    BARRIER();bench_data.marker=2;BARRIER();
#if BENCH_MODE != 0
    bench_data.hw_cycles=FIR[5];bench_data.hw_written=FIR[6];
#endif
    for(u32 n=0;n<SAMPLE_COUNT;++n)if(bench_data.outputs[n]!=bench_data.expected[n])++errors;
    bench_data.errors=errors;bench_data.done=1;
    return (int)errors;
}
