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
    coefficients = bench_data + 4096;
    outputs = bench_data + 4224;
    expected = bench_data + 8320;
    marker = bench_data + 12416;
    done = bench_data + 12420;
    errors = bench_data + 12424;
    polls = bench_data + 12428;
    hw_cycles = bench_data + 12432;
    hw_written = bench_data + 12436;
    /DISCARD/ : {*(.eh_frame*) *(.comment)}
}
