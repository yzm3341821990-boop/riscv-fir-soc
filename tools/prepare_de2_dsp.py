"""Create a new DSP6 candidate, without invoking Quartus or JTAG."""
import argparse,json,shutil
from pathlib import Path
from tools.prepare_de2_app import SOURCES as APP_SOURCES,ROOT,digest
SOURCES=tuple(s.replace('pipeline_app_cpu','pipeline_dsp_cpu').replace('de2_115_app_','de2_115_dsp_') for s in APP_SOURCES[:-2])+(
    'rtl/fir/fir_serial.vhd','rtl/fir/fir_mmio_large.vhd','rtl/soc/dsp_profiler.vhd',
    'rtl/board/de2_115_dsp_core.vhd','rtl/board/de2_115_dsp_top.vhd')
def prepare(output,firmware):
    d=Path(output).resolve()
    if d.exists() and any(d.iterdir()):raise ValueError('Use a new empty directory')
    d.mkdir(parents=True,exist_ok=True)
    for s in SOURCES:shutil.copyfile(ROOT/s,d/Path(s).name)
    base=(ROOT/'fpga/de2_machine/board.qsf').read_text(encoding='ascii')
    qsf='\n'.join(s for s in base.splitlines() if not any(k in s for k in ('VHDL_FILE','SDC_FILE','TOP_LEVEL_ENTITY','PARTITION_','PARTITION_COLOR')))+'\n'
    qsf+='set_global_assignment -name TOP_LEVEL_ENTITY de2_115_dsp_top\nset_global_assignment -name SDC_FILE dsp.sdc\nset_global_assignment -name SDC_FILE jtag.sdc\n'
    qsf+=''.join('set_global_assignment -name VHDL_FILE '+Path(s).name+'\n' for s in SOURCES)
    (d/'riscv_cpu_dsp.qsf').write_text(qsf,encoding='ascii');(d/'riscv_cpu_dsp.qpf').write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "riscv_cpu_dsp"\n',encoding='ascii')
    sdc=(ROOT/'fpga/de2_display/display.sdc').read_text(encoding='ascii')+'\nset jtag_first [get_registers {*|mailbox|source_meta*}]\nif {[get_collection_size $jtag_first] != 320} {error "DSP6_CDC_FIRST_STAGE_COUNT"}\nset_false_path -to $jtag_first\n'
    (d/'dsp.sdc').write_text(sdc,encoding='ascii');shutil.copyfile(ROOT/'fpga/de2_visual/jtag.sdc',d/'jtag.sdc')
    shutil.copytree(firmware,d/'firmware')
    (d/'live_link_lib.tcl').write_text((ROOT/'host/app_link_lib.tcl').read_text().replace('CPU5','DSP6').replace('step33','step36'),encoding='ascii')
    shutil.copyfile(ROOT/'host/live_service.tcl',d/'live_service.tcl')
    from tools.prepare_de2_app import TOOLS,MODELS
    for group,names in [('tools',(*TOOLS,'dsp_console','dsp_session','dsp_program','open_dsp_console')),('model',(*MODELS,'dsp_machine','dsp_peripheral'))]:
        folder=d/'desktop'/group;folder.mkdir(parents=True,exist_ok=True);(folder/'__init__.py').write_text('',encoding='ascii')
        for n in dict.fromkeys(names):shutil.copyfile(ROOT/group/(n+'.py'),folder/(n+'.py'))
    (d/'desktop/web').mkdir();shutil.copyfile(ROOT/'web/dsp_console.html',d/'desktop/web/dsp_console.html')
    (d/'desktop/launch_dsp.py').write_text('from tools.dsp_console import main\nif __name__=="__main__":main()\n',encoding='ascii')
    (d/'Open-DSP6.cmd').write_text('@echo off\npython "%~dp0desktop\\tools\\open_dsp_console.py" --project "%~dp0."\nif errorlevel 1 pause\n',encoding='ascii')
    preview=ROOT/'reports/step36-dsp-c/rtl-preview.json'
    if preview.is_file():shutil.copyfile(preview,d/'rtl-preview.json')
    m=dict(image='DSP6',identity='44535036',abi='00360001',fir_lanes=4,clock_hz=25000000,device='EP4CE115F29C7',source_sha256={s:digest(ROOT/s) for s in SOURCES},hardware_input_sha256={p.name:digest(p) for p in d.iterdir() if p.suffix in ('.vhd','.qsf','.qpf','.sdc')},firmware_elf_sha256=digest(d/'firmware/program.elf'),quartus='not_run',sof='not_generated',physical='not_tested')
    (d/'dsp-project-manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--firmware',required=True);a=p.parse_args();print(json.dumps(prepare(a.output,a.firmware)))
