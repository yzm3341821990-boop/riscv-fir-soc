"""Prepare isolated 1/2/4-lane Quartus projects without invoking vendor tools."""
import argparse
import json
from pathlib import Path

from tools.prepare_de2_pipeline import ROOT,PROJECT as BASE_PROJECT,prepare as prepare_base,digest


def prepare(directory,lanes):
    if type(lanes) is not int or lanes not in (1,2,4):raise ValueError('lanes must be 1, 2 or 4')
    directory=Path(directory)
    if any((directory/'output_files').glob('*.sof')):
        raise FileExistsError('Preserve the compiled image; generate into a new directory')
    existing=list(directory.glob('*.qpf'))
    project=f'riscv_fir_de2_p{lanes}'
    if any(p.stem!=project for p in existing):raise FileExistsError('Different existing project: '+str(existing))
    manifest=prepare_base(directory)
    qsf=(directory/(BASE_PROJECT+'.qsf')).read_text()+'set_parameter -name FIR_LANES '+str(lanes)+'\n'
    (directory/(project+'.qsf')).write_text(qsf,encoding='ascii')
    (directory/'pipeline-qsf-before-build.txt').write_text(qsf,encoding='ascii')
    (directory/(project+'.qpf')).write_text('QUARTUS_VERSION = "17.0"\nPROJECT_REVISION = "'+project+'"\n',encoding='ascii')
    for extension in ('.qpf','.qsf'):
        (directory/(BASE_PROJECT+extension)).unlink()
        manifest['generated_sha256'].pop(BASE_PROJECT+extension)
    macro=directory/'run_pipeline_board_batch.do'
    macro.write_text(macro.read_text().replace('work.tb_de2_pipeline\n',f'-gFIR_LANES={lanes} work.tb_de2_pipeline\n'),encoding='ascii')
    names=[*manifest['generated_sha256'],project+'.qsf',project+'.qpf']
    manifest.update(contract='fir-parallel-lanes-v1',project=project,mac_lanes=lanes,
        source_sha256={**manifest['source_sha256'],
            'tools/prepare_de2_parallel.py':digest(ROOT/'tools/prepare_de2_parallel.py'),
            'docs/parallel-fir-contract.md':digest(ROOT/'docs/parallel-fir-contract.md')},
        generated_sha256={name:digest(directory/name) for name in names},
        scope='Parallel FIR candidate. Quartus compilation and hardware observation pending for this image.')
    (directory/'project-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--lanes',type=int,choices=(1,2,4),required=True)
    a=p.parse_args();d=a.output.resolve()
    if not str(d).isascii() or any(c in str(d) for c in '{}\r\n'):p.error('ASCII output path required')
    m=prepare(d,a.lanes)
    print(json.dumps(dict(project=str(d/(m['project']+'.qpf')),lanes=a.lanes,quartus_compiled=False),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
