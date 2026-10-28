OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
    ROM (rx) : ORIGIN = 0, LENGTH = 512
    RAM (rw) : ORIGIN = 512, LENGTH = 512
}
PHDRS {
    text PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}
SECTIONS {
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
        . = ALIGN(4);
        _program_end = .;
    } > ROM :text
    .data : {
        . = ALIGN(4);
        *(.sdata .sdata.* .data .data.*)
    } > RAM :data
    .bss (NOLOAD) : {
        . = ALIGN(4);
        *(.sbss .sbss.* .bss .bss.*)
        *(COMMON)
    } > RAM :data
    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(bench_data == 512, "benchmark object must start at RAM byte 512")
    ASSERT(. <= _stack_top - 128, "reserve at least 128 bytes for the stack")
    samples = bench_data;
    coefficients = bench_data + 32;
    outputs = bench_data + 160;
    marker = bench_data + 192;
    done = bench_data + 196;
    errors = bench_data + 200;
    polls = bench_data + 204;
    hw_cycles = bench_data + 208;
    hw_written = bench_data + 212;
    /DISCARD/ : { *(.eh_frame*) *(.comment) }
}
