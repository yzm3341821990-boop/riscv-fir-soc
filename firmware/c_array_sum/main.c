/* Freestanding RV32I demonstration; volatile prevents folding the RAM reads. */
_Static_assert(sizeof(short) == 2 && sizeof(int) == 4, "requires ILP32");

volatile short samples[8] = {12, -3, 25, -10, 7, -2, 30, -4};
volatile int result;
volatile unsigned int done;

__attribute__((noinline))
int sum_samples(volatile const short *data, unsigned int count)
{
    int total = 0;
    for (unsigned int i = 0; i < count; ++i)
        total += data[i];
    return total;
}

int main(void)
{
    result = sum_samples(samples, 8);
    done = 1;
    return result;
}
