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
    ASSERT(. <= _stack_top - 128, "reserve at least 128 bytes for the stack")
    /DISCARD/ : { *(.eh_frame*) *(.comment) }
}
