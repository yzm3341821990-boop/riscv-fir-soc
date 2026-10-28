/* fir-mmio-1k-v1: volatile, aligned 32-bit MMIO and Q15 RAM words. */
typedef unsigned int u32;
#define FIR ((volatile u32 *)0x40003000u)
volatile int samples[8] = {16384,32767,-32768,8192,-16384,24576,0,-8192};
volatile int coefficients[32] = {16384,-8192,4096,2048};
volatile int expected[8] = {8192,12288,-22528,17408,-12288,15360,-7680,-2048};
volatile int outputs[8];
volatile u32 done, errors, polls, hw_cycles, hw_written;

int main(void) {
    FIR[0] = 2; /* acknowledge previous status */
    for (u32 k=0; k<32; ++k) FIR[64+k] = (u32)coefficients[k];
    FIR[2] = (u32)samples;
    FIR[3] = (u32)outputs;
    FIR[4] = 8;
    FIR[0] = 1;
    u32 status;
    do {
        status = FIR[1];
        ++polls;
    } while ((status & 1u) && polls < 64u);
    /* A timeout does not transfer the still-running DMA's buffer ownership. */
    if (status != 2u) { errors = 1; done = 1; return 1; }
    for (u32 n=0; n<8; ++n) if (outputs[n] != expected[n]) ++errors;
    hw_cycles = FIR[5];
    hw_written = FIR[6];
    done = 1;
    return (int)errors;
}
