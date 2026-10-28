/* Q15 block FIR: 32 taps, zero history, one output per input, no tail. */
_Static_assert(sizeof(short)==2 && sizeof(int)==4 && sizeof(long long)==8, "requires ILP32");
volatile short samples[8] = {16384,32767,-32768,8192,-16384,24576,0,-8192};
volatile short coefficients[32] = {16384,-8192,4096,2048};
volatile short outputs[8];
volatile long long accumulators[8];
volatile unsigned int done;

static short quantize(long long accumulator)
{
    long long magnitude = accumulator < 0 ? -accumulator : accumulator;
    int value = (int)((magnitude + 16384) >> 15);
    if (accumulator < 0) value = -value;
    if (value > 32767) value = 32767;
    if (value < -32768) value = -32768;
    return (short)value;
}

__attribute__((noinline))
void fir_q15(void)
{
    for (unsigned int n=0; n<8; ++n) {
        long long accumulator=0;
        for (unsigned int k=0; k<32 && k<=n; ++k) {
            int product=(int)samples[n-k] * (int)coefficients[k];
            accumulator += (long long)product;
        }
        accumulators[n]=accumulator;
        outputs[n]=quantize(accumulator);
    }
}

int main(void)
{
    fir_q15();
    done=1;
    return outputs[7];
}
