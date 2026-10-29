"""Build fixed 32 KiB C firmware and all-result golden images, without Quartus."""
import argparse,hashlib,json,random,shutil,struct,subprocess
from pathlib import Path
from model.fixed_fir import fir_block
from tools.build_c_demo import DEFAULT_ZIG
from tools.build_fir_benchmark import BENCH_FLAGS,MODES,validate_instructions
from tools.large_elf import read_large_elf

ROOT=Path(__file__).resolve().parents[1]


def layout(n):
    if type(n) is not int or n not in (64,256,1024):raise ValueError('supported lengths: 64, 256, 1024')
    base=2048
    result={'samples':base,'coefficients':base+4*n,'outputs':base+4*n+128,
            'expected':base+8*n+128,'marker':base+12*n+128}
    result.update({name:result['marker']+4*k for k,name in enumerate(['marker','done','errors','polls','hw_cycles','hw_written'])})
    result['_stack_top']=32768
    return result


def dataset(n):
    rng=random.Random(20261029)
    coefficients=[rng.choice([v for v in range(-4096,4097) if v]) for _ in range(32)]
    samples=[rng.randint(-32768,32767) for _ in range(1024)]
    samples[0],samples[1],samples[31],samples[32]=32767,-32768,-32768,32767
    x=samples[:n];golden=fir_block(x,coefficients)
    independent=[]
    for i in range(n):
        total=sum(coefficients[k]*x[i-k] for k in range(32) if k<=i)
        magnitude=(abs(total)+16384)//32768
        value=-magnitude if total<0 else magnitude
        independent.append(max(-32768,min(32767,value)))
    if independent!=list(golden.outputs):raise ValueError('independent long convolution disagrees')
    return x,coefficients,list(golden.outputs)


def linker(n):
    syms=layout(n)
    aliases='\n'.join(f'    {name} = bench_data + {address-2048};' for name,address in syms.items() if name!='_stack_top')
    return '''OUTPUT_ARCH(riscv)
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
'''+aliases+'''
    /DISCARD/ : {*(.eh_frame*) *(.comment)}
}
'''


def build(n,zig,directory,output):
    syms=layout(n);directory=Path(directory);output=Path(output);zig=Path(zig)
    directory.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    x,h,y=dataset(n);manifests={};initials=[]
    version=subprocess.run([str(zig),'version'],capture_output=True,text=True,timeout=15)
    if version.returncode or version.stdout.strip()!='0.13.0':raise ValueError('requires Zig 0.13.0')
    for mode,number in MODES.items():
        work=directory/mode;work.mkdir(exist_ok=True)
        shutil.copyfile(ROOT/'firmware/fir_large/main.c',work/'main.c')
        shutil.copyfile(ROOT/'firmware/c_array_sum/start.S',work/'start.S')
        (work/'link.ld').write_text(linker(n),encoding='ascii')
        flags=[*BENCH_FLAGS,f'-DSAMPLE_COUNT={n}',f'-DBENCH_MODE={number}']
        commands=[['cc',*flags,'-nostdlib','-Wl,-T,link.ld','-Wl,--build-id=none','start.S','main.c','-o','program.elf'],
                  ['cc',*flags,'-S','main.c','-o','main.s']]
        for command in commands:
            p=subprocess.run([str(zig),*command],cwd=work,capture_output=True,text=True,errors='replace',timeout=120)
            if p.returncode or p.stderr.strip():raise RuntimeError(p.stdout+p.stderr)
        image=read_large_elf((work/'program.elf').read_bytes());validate_instructions(image.program_words)
        if any(image.symbols.get(k)!=v for k,v in syms.items()):raise ValueError('long firmware layout mismatch')
        memory=bytearray(struct.pack('<8192I',*image.memory_words))
        for name,values in [('samples',x),('coefficients',h),('expected',y)]:
            struct.pack_into('<'+str(len(values))+'i',memory,syms[name],*values)
        initials.append(bytes(memory))
        (work/'program.hex').write_text(''.join(f'{v:08X}\n' for v in image.program_words),encoding='ascii')
        (work/'initial_memory.txt').write_text(''.join(f'{v:08X}\n' for v in struct.unpack('<8192I',memory)),encoding='ascii')
        artifact={name:hashlib.sha256((work/name).read_bytes()).hexdigest() for name in ['program.elf','program.hex','initial_memory.txt','main.s','link.ld']}
        manifest={'contract':'fir-large-block-v1','sample_count':n,'mode':mode,'layout':syms,'symbols':image.symbols,
            'program_words':len(image.program_words),'ram_words':8192,'compiler_version':'Zig 0.13.0 / Clang 18.1.6',
            'compiler_sha256':hashlib.sha256(zig.read_bytes()).hexdigest(),'compiler_flags':BENCH_FLAGS,
            'commands':commands,'initial_memory_sha256':hashlib.sha256(memory).hexdigest(),
            'samples':x,'coefficients':h,'expected_outputs':y,'artifact_sha256':artifact,
            'input_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                ['firmware/fir_large/main.c','firmware/c_array_sum/start.S','tools/build_large_firmware.py','tools/large_elf.py']}}
        (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        destination=output/mode;destination.mkdir(exist_ok=True)
        for name in [*artifact,'manifest.json']:shutil.copyfile(work/name,destination/name)
        manifests[mode]=manifest
    if len(set(initials))!=1:raise ValueError('long benchmark modes have different initial RAM')
    return manifests


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path,default=DEFAULT_ZIG)
    p.add_argument('--build-dir',type=Path,default=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_firmware'))
    p.add_argument('--output',type=Path,default=ROOT/'programs/fir_large')
    a=p.parse_args()
    for n in [64,256,1024]:
        result=build(n,a.zig,a.build_dir/f'n{n}',a.output/f'n{n}')
        print(json.dumps({'samples':n,'program_words':{k:v['program_words'] for k,v in result.items()}}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
