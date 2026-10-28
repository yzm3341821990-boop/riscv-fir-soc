/* One source, one RAM layout, three matched FIR invocation measurements. */
typedef unsigned int u32;
_Static_assert(sizeof(int)==4 && sizeof(long long)==8, "requires ILP32 and signed64 C accumulator");
#ifndef BENCH_MODE
#error "BENCH_MODE must select software=0, hardware_cold=1, hardware_resident=2"
#endif
#define FIR ((volatile u32 *)0x40003000u)
#define BARRIER() __asm__ volatile ("" ::: "memory")

struct benchmark_data {
    int samples[8];
    int coefficients[32];
    int outputs[8];
    volatile u32 marker, done, errors, polls, hw_cycles, hw_written;
};
_Static_assert(sizeof(struct benchmark_data)==216, "fixed shared RAM object size");
_Static_assert(__builtin_offsetof(struct benchmark_data, coefficients)==32, "coefficient offset");
_Static_assert(__builtin_offsetof(struct benchmark_data, outputs)==160, "output offset");
_Static_assert(__builtin_offsetof(struct benchmark_data, marker)==192, "marker offset");
struct benchmark_data bench_data = {
    .samples = {16384,32767,-32768,8192,-16384,24576,0,-8192},
    .coefficients = {16384,-8192,4096,2048}
};

#if BENCH_MODE == 0
static int quantize(long long accumulator)
{
    long long magnitude = accumulator < 0 ? -accumulator : accumulator;
    int value = (int)((magnitude + 16384) >> 15);
    if (accumulator < 0) value = -value;
    if (value > 32767) value = 32767;
    if (value < -32768) value = -32768;
    return value;
}

__attribute__((noinline)) int run_fir(void)
{
    for (u32 n=0; n<8; ++n) {
        long long accumulator = 0;
        for (u32 k=0; k<32 && k<=n; ++k) {
            /* Signed16 operands guarantee this full signed32 product fits. */
            int product = bench_data.samples[n-k] * bench_data.coefficients[k];
            accumulator += (long long)product;
        }
        bench_data.outputs[n] = quantize(accumulator);
    }
    return 0;
}
#else
static void load_coefficients(void)
{
    for (u32 k=0; k<32; ++k) FIR[64+k] = (u32)bench_data.coefficients[k];
}

__attribute__((noinline)) int run_fir(void)
{
    FIR[0] = 2;
#if BENCH_MODE == 1
    load_coefficients();
#endif
    FIR[2] = (u32)bench_data.samples;
    FIR[3] = (u32)bench_data.outputs;
    FIR[4] = 8;
    FIR[0] = 1;
    u32 status, count = 0;
    do {
        status = FIR[1];
        ++count;
    } while ((status & 1u) && count < 64u);
    bench_data.polls = count;
    return status != 2u;
}
#endif

int main(void)
{
#if BENCH_MODE == 2
    /* This setup is deliberately outside the resident-coefficient interval. */
    load_coefficients();
#endif
    BARRIER();
    bench_data.marker = 1;
    BARRIER();
    bench_data.errors = (u32)run_fir();
    BARRIER();
    bench_data.marker = 2;
    BARRIER();
#if BENCH_MODE != 0
    /* Diagnostic register reads are outside the full invocation interval. */
    bench_data.hw_cycles = FIR[5];
    bench_data.hw_written = FIR[6];
#endif
    bench_data.done = 1;
    return (int)bench_data.errors;
}
