"""Prepare independent CPU5 QPF and desktop application, without Quartus/JTAG."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=(
    'rtl/cpu/alu_pkg.vhd',
    'rtl/cpu/alu32.vhd',
    'rtl/cpu/regfile32.vhd',
    'rtl/cpu/mul32.vhd',
    'rtl/cpu/imm_i.vhd',
    'rtl/cpu/imm_s.vhd',
    'rtl/cpu/imm_b.vhd',
    'rtl/cpu/imm_j.vhd',
    'rtl/cpu/imm_u.vhd',
    'rtl/cpu/decode_tiny.vhd',
    'rtl/cpu/data_ram.vhd',
    'rtl/cpu/rv32m_unit.vhd',
    'rtl/cpu/pipeline_app_cpu.vhd',
    'rtl/soc/shared_ram_m9k.vhd',
    'rtl/board/hex7seg.vhd',
    'rtl/board/jtag_live_mailbox.vhd',
    'rtl/soc/machine_timer.vhd',
    'rtl/soc/instruction_ram16k_m9k.vhd',
    'rtl/board/de2_115_app_core.vhd',
    'rtl/board/de2_115_app_top.vhd',
)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

TOOLS=('app_protocol','app_session','app_program','app_elf','app_console','build_app','open_app_console','build_c_demo','elf32','runner_protocol','live_protocol','live_session')
MODELS=('app_machine','tiny_cpu','alu','fixed_fir','rv32m')

def prepare(output,firmware):
    d=Path(output).resolve();firmware=Path(firmware)
    if d.exists() and any(d.iterdir()):raise ValueError('Use a new empty project directory')
    d.mkdir(parents=True,exist_ok=True)
    for src in SOURCES:shutil.copyfile(ROOT/src,d/Path(src).name)
    base=(ROOT/'fpga/de2_machine/board.qsf').read_text(encoding='ascii')
    qsf='\n'.join(s for s in base.splitlines() if not any(k in s for k in ('VHDL_FILE','SDC_FILE','TOP_LEVEL_ENTITY','PARTITION_','PARTITION_COLOR')))+'\n'
    qsf+='set_global_assignment -name TOP_LEVEL_ENTITY de2_115_app_top\nset_global_assignment -name SDC_FILE app.sdc\nset_global_assignment -name SDC_FILE jtag.sdc\n'
    qsf+=''.join('set_global_assignment -name VHDL_FILE '+Path(s).name+'\n' for s in SOURCES)
    (d/'riscv_cpu_app.qsf').write_text(qsf,encoding='ascii');(d/'riscv_cpu_app.qpf').write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "riscv_cpu_app"\n',encoding='ascii')
    sdc=(ROOT/'fpga/de2_display/display.sdc').read_text(encoding='ascii')+'\nset jtag_first [get_registers {*|mailbox|source_meta*}]\nif {[get_collection_size $jtag_first] != 320} {error "CPU5_CDC_FIRST_STAGE_COUNT"}\nset_false_path -to $jtag_first\n'
    (d/'app.sdc').write_text(sdc,encoding='ascii');shutil.copyfile(ROOT/'fpga/de2_visual/jtag.sdc',d/'jtag.sdc')
    for n in ('number_lab','matrix','fir'):shutil.copytree(firmware/n,d/'examples'/n)
    for group,names in [('tools',TOOLS),('model',MODELS)]:
        folder=d/'desktop'/group;folder.mkdir(parents=True,exist_ok=True);(folder/'__init__.py').write_text('',encoding='ascii')
        for n in names:shutil.copyfile(ROOT/group/(n+'.py'),folder/(n+'.py'))
    shutil.copytree(ROOT/'firmware/app_runtime',d/'desktop/firmware/app_runtime')
    (d/'desktop/web').mkdir();shutil.copyfile(ROOT/'web/app_console.html',d/'desktop/web/app_console.html')
    (d/'desktop/launch_app.py').write_text('from tools.app_console import main\nif __name__=="__main__":main()\n',encoding='ascii')
    shutil.copyfile(ROOT/'host/app_link_lib.tcl',d/'live_link_lib.tcl');shutil.copyfile(ROOT/'host/live_service.tcl',d/'live_service.tcl')
    (d/'Open-CPU5.cmd').write_text('@echo off\npython "%~dp0desktop\\tools\\open_app_console.py" --project "%~dp0."\nif errorlevel 1 pause\n',encoding='ascii')
    preview=ROOT/'reports/step33-app-platform/rtl-preview.json'
    if preview.is_file():shutil.copyfile(preview,d/'rtl-preview.json')
    # The launcher has no package imports; background launch adds desktop to sys.path.
    manifest=dict(instance='CPU5',identity='43505535',abi='00330001',clock_hz=25000000,device='EP4CE115F29C7',
        source_sha256={s:digest(ROOT/s) for s in SOURCES},hardware_input_sha256={p.name:digest(p) for p in d.iterdir() if p.suffix in ('.vhd','.sdc','.qpf','.qsf')},
        generated_sha256={p.relative_to(d).as_posix():digest(p) for p in d.rglob('*') if p.is_file()},quartus='not_run',sof='not_generated',physical='not_tested')
    (d/'app-project-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--firmware',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.firmware)))
