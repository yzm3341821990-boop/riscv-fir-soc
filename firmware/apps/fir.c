#include "cpu5.h"
int main(void) {
    uint32_t n=job.input_count;if(n>128)return 2;
    for(uint32_t i=0;i<n;i++) {
        int64_t sum=0;
        for(unsigned k=0;k<16;k++)if(i>=k)sum+=(int64_t)job.input[i-k]*2048;
        int64_t y=sum>>15;
        if(y>2147483647)y=2147483647;
        if(y<(-2147483647-1))y=(-2147483647-1);
        job.output[i]=(int32_t)y;
    }
    job.output_count=n;cpu5_puts("CPU5 C FIR: 16 taps / Q15\nSoftware on RV32M; no FIR accelerator used\n");return 0;
}
