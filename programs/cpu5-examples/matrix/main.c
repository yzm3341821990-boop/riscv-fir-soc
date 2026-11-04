#include "cpu5.h"
int main(void) {
    if(job.input_count!=128)return 2;
    for(unsigned r=0;r<8;r++)for(unsigned c=0;c<8;c++) {
        uint32_t sum=0;
        for(unsigned k=0;k<8;k++)sum+=(uint32_t)job.input[8*r+k]*(uint32_t)job.input[64+8*k+c];
        job.output[8*r+c]=(int32_t)sum;
    }
    job.output_count=64;cpu5_puts("CPU5: 8 x 8 matrix product\n64 values, arithmetic modulo 2^32\n");return 0;
}
