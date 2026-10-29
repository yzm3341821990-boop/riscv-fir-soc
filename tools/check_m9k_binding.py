"""Analyze RAM against the installed synthesis component interface, without Quartus."""
import hashlib,json,shutil,subprocess
from pathlib import Path
from tools.run_large_soc import ROOT

OUT=Path('F:/CodexWorkspace/outputs/riscv-fir-soc/large_soc/component-binding')
PACKAGE=Path('E:/quartus/quartus/libraries/vhdl/altera_mf/altera_mf_components.vhd')
EXE=Path('E:/quartus/modelsim_ase/win32aloem/vsim.exe')


def analyze(name,source):
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(PACKAGE,folder/'altera_mf_components.vhd')
    (folder/'shared_ram_m9k.vhd').write_text(source,encoding='ascii')
    script='''onerror {quit -code 1 -f}
if {![file exists modelsim.ini]} {vmap -c}
if {![file isdirectory mf_interfaces]} {vlib mf_interfaces}
if {![file isdirectory work]} {vlib work}
vmap altera_mf mf_interfaces
vmap work work
vcom -93 -work altera_mf altera_mf_components.vhd
vcom -93 shared_ram_m9k.vhd
echo M9K_COMPONENT_INTERFACE_ANALYSIS_PASS
quit -code 0 -f
'''
    (folder/'check.do').write_text(script,encoding='ascii')
    result=subprocess.run([str(EXE),'-c','-l','binding.log','-do','do check.do'],cwd=folder,
        capture_output=True,text=True,errors='replace',timeout=60)
    return result.returncode,(folder/'binding.log').read_text(errors='replace')


def main():
    report_dir=ROOT/'reports/step20-large-block';report_file=report_dir/'binding-validation.json'
    report_file.write_text('{"status":"incomplete"}\n')
    source=(ROOT/'rtl/soc/shared_ram_m9k.vhd').read_text(encoding='ascii')
    legacy=source.replace('use altera_mf.altera_mf_components.all;\n','').replace('memory : altsyncram','memory : entity altera_mf.altsyncram')
    rc,log=analyze('legacy_entity',legacy);(report_dir/'binding-legacy-entity.log').write_text(log,encoding='utf-8')
    if rc==0 or 'altsyncram' not in log or '** Error:' not in log:raise ValueError('legacy interface control did not fail as expected')
    code,good=analyze('component_interface',source);(report_dir/'binding-component-interface.log').write_text(good,encoding='utf-8')
    if code or 'M9K_COMPONENT_INTERFACE_ANALYSIS_PASS' not in good or any(s in good for s in ['** Error:','** Warning:']):
        raise ValueError('component-only interface analysis failed\n'+good[-2400:])
    report=dict(status='pass',interface_package=str(PACKAGE),interface_sha256=hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
        legacy_direct_entity_rejected=True,current_component_analyzed=True,
        scope='ModelSim VHDL-93 analysis against the actual installed Quartus synthesis component declarations only. No vendor entity is present in this isolated library. This is not a Quartus synthesis pass.',
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['rtl/soc/shared_ram_m9k.vhd','tools/check_m9k_binding.py']},
        quartus='awaiting_user_recompile',hardware='not_run')
    report_file.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print('M9K_COMPONENT_BINDING_PASS legacy_control_rejected=true');return 0


if __name__=='__main__':raise SystemExit(main())
