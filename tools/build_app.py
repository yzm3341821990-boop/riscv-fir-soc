"""Compile bounded user C with the installed compiler; no hardware calls."""
import os,hashlib,json,shutil,subprocess
from pathlib import Path
from tools.build_c_demo import FLAGS
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_ZIG=Path(os.environ.get("RISCV_ZIG") or shutil.which("zig") or "zig")

def build(source,directory,zig=DEFAULT_ZIG):
    if not isinstance(source,str) or not 1<=len(source.encode('utf-8'))<=60000:raise ValueError('C source must be 1..60000 bytes')
    d=Path(directory).resolve();d.mkdir(parents=True,exist_ok=True)
    if not str(d).isascii():raise ValueError('Use an ASCII build path')
    for name in ('cpu5.h','start.S','link.ld'):shutil.copyfile(ROOT/'firmware/app_runtime'/name,d/name)
    (d/'main.c').write_text(source,encoding='utf-8')
    flags=[v.replace('generic_rv32','generic_rv32+m+zicsr') for v in FLAGS]
    command=[str(zig),'cc',*flags,'-Wall','-Wextra','-Werror','-nostdlib','-Wl,-T,link.ld','-Wl,--build-id=none','start.S','main.c','-o','program.elf']
    p=subprocess.run(command,cwd=d,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=40)
    diagnostics=p.stdout+p.stderr;(d/'compiler.log').write_text(diagnostics,encoding='utf-8')
    if p.returncode:raise ValueError(diagnostics or 'C compilation failed')
    from tools.app_program import program_image
    image=program_image((d/'program.elf').read_bytes())
    (d/'program.hex').write_text(''.join(f'{v:08X}\n' for v in image.program_words),encoding='ascii')
    manifest=dict(format='cpu5-c-build-v1',source_sha256=hashlib.sha256(source.encode()).hexdigest(),elf_sha256=hashlib.sha256((d/'program.elf').read_bytes()).hexdigest(),text_bytes=len(image.program_words)*4,
        command=command,compiler_sha256=hashlib.sha256(Path(zig).read_bytes()).hexdigest(),runtime_sha256={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in ('cpu5.h','start.S','link.ld')},diagnostics=diagnostics)
    (d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');return manifest
