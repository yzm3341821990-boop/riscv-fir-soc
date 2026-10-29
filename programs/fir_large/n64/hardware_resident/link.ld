OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {ROM (rx) : ORIGIN = 0, LENGTH = 1024
        RAM (rw) : ORIGIN = 2048, LENGTH = 30720}
PHDRS {text PT_LOAD FLAGS(5);data PT_LOAD FLAGS(6);}
SECTIONS {
    .text : {KEEP(*(.text.start)) *(.text .text.*) . = ALIGN(4); _program_end = .;} > ROM :text
    .data : {. = ALIGN(4); *(.sdata .sdata.* .data .data.*)} > RAM :data
    .bss (NOLOAD) : {. = ALIGN(4); *(.sbss .sbss.* .bss .bss.*) *(COMMON)} > RAM :data
    _stack_top = 32768;
    ASSERT(bench_data == 2048, "shared object address")
    ASSERT(. <= _stack_top-512, "reserve stack")
    samples = bench_data + 0;
    coefficients = bench_data + 256;
    outputs = bench_data + 384;
    expected = bench_data + 640;
    marker = bench_data + 896;
    done = bench_data + 900;
    errors = bench_data + 904;
    polls = bench_data + 908;
    hw_cycles = bench_data + 912;
    hw_written = bench_data + 916;
    /DISCARD/ : {*(.eh_frame*) *(.comment)}
}
