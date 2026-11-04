#include "cpu5.h"
int main(void) {
    for (unsigned i=0;i<job.input_count;i++) {
        uint32_t v=(uint32_t)job.input[i];
        job.output[i]=(int32_t)(v*v+7u);
    }
    job.output_count=job.input_count;
    cpu5_puts("Python called my CPU: square + 7\n");
    return 0;
}
