OUTPUT_ARCH(riscv)
ENTRY(_start)
PHDRS { code PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }
MEMORY { ROM (rx) : ORIGIN = 0, LENGTH = 16380
         RAM (rw) : ORIGIN = 0x10000000, LENGTH = 32768 }
SECTIONS {
    .text : { KEEP(*(.text.start)) *(.text .text.*) . = ALIGN(4); } > ROM :code
    _program_end = .;
    .job (NOLOAD) : { KEEP(*(.job)) } > RAM :data
    .data : { *(.rodata .rodata.*) *(.data .data.*) *(.sdata .sdata.*) } > RAM :data
    .bss (NOLOAD) : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) . = ALIGN(16); } > RAM :data
    _data_end = .;
    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(_data_end <= _stack_top - 2048, "CPU5 RAM needs 2 KiB reserved stack")
    /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.eh_frame*) }
}
