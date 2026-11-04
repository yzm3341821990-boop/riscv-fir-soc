#include "cpu5.h"
static uint32_t gcd(uint32_t a,uint32_t b) { while(b) {uint32_t t=a%b;a=b;b=t;}return a; }
static uint32_t root(uint32_t v) {
    uint32_t r=0,bit=1u<<30;while(bit>v)bit>>=2;
    while(bit){if(v>=r+bit){v-=r+bit;r=(r>>1)+bit;}else r>>=1;bit>>=2;}return r;
}
static uint32_t reverse(uint32_t x) {
    x=((x&0x55555555u)<<1)|((x>>1)&0x55555555u);
    x=((x&0x33333333u)<<2)|((x>>2)&0x33333333u);
    x=((x&0x0f0f0f0fu)<<4)|((x>>4)&0x0f0f0f0fu);
    x=((x&0x00ff00ffu)<<8)|((x>>8)&0x00ff00ffu);return (x<<16)|(x>>16);
}
int main(void) {
    uint32_t n=job.input_count;if(n>112)return 2;
    uint32_t sum=0,g=0,hash=2166136261u,crc=0xffffffffu,bits=0;
    for(uint32_t i=0;i<n;i++) {
        int32_t v=job.input[i];job.output[i]=v;sum+=(uint32_t)v;
        uint32_t u=(uint32_t)v;g=gcd(g,v<0?0u-u:u);
        hash=(hash^u)*16777619u;
        for(unsigned k=0;k<32;k++){bits+=(u>>k)&1u;uint32_t mix=(crc^(u>>k))&1u;crc=(crc>>1)^(0xedb88320u*(mix));}
    }
    for(uint32_t i=1;i<n;i++) {
        int32_t v=job.output[i];uint32_t k=i;
        while(k && job.output[k-1]>v){job.output[k]=job.output[k-1];k--;}
        job.output[k]=v;
    }
    job.output[n]=(int32_t)sum;job.output[n+1]=n?job.output[0]:0;
    job.output[n+2]=n?job.output[n-1]:0;job.output[n+3]=(int32_t)g;
    job.output[n+4]=(int32_t)hash;job.output[n+5]=(int32_t)~crc;
    job.output[n+6]=(int32_t)bits;job.output[n+7]=(int32_t)root(sum);
    job.output[n+8]=(int32_t)reverse(sum);job.output_count=n+9;
    cpu5_puts("CPU5 integer lab: sorted ");cpu5_print_u32(n);
    cpu5_puts(" values\nsum=");cpu5_print_i32((int32_t)sum);
    cpu5_puts(" gcd=");cpu5_print_u32(g);cpu5_puts(" bits=");cpu5_print_u32(bits);
    cpu5_puts("\ncrc32=");cpu5_print_u32(~crc);cpu5_puts("\n");return 0;
}
