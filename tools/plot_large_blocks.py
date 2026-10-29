"""Plot only recorded, matched long-block measurements; export shareable figures."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from tools.run_large_soc import ROOT
from tools.compare_large_blocks import compare


def main():
    source=ROOT/'reports/step20-large-block/system-validation.json';report=json.loads(source.read_text());rows=compare(report)
    destination=ROOT/'artifacts/step20';destination.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,3,figsize=(14,5.8),sharey=True)
    fig.subplots_adjust(left=.065,right=.99,top=.82,bottom=.28,wspace=.06)
    colors=['#627080','#477CB6','#477CB6','#477CB6','#258C79','#258C79','#258C79']
    x=[0,1.3,2.1,2.9,4.2,5,5.8]
    for axis,n in zip(axes,[64,256,1024]):
        cold=[next(r for r in rows if (r['sample_count'],r['mode'],r['lanes'],r['dma_wait'])==(n,'hardware_cold',p,'none')) for p in [1,2,4]]
        resident=[next(r for r in rows if (r['sample_count'],r['mode'],r['lanes'],r['dma_wait'])==(n,'hardware_resident',p,'none')) for p in [1,2,4]]
        values=[cold[0]['software_cycles']]+[r['complete_call_cycles'] for r in cold+resident]
        axis.bar(x,values,width=.64,color=colors,zorder=3)
        for position,value in zip(x,values):axis.text(position,value*1.14,f'{value:,}',ha='center',va='bottom',fontsize=8)
        axis.set(yscale='log',ylim=(300,1000000),xticks=x,xticklabels=['C','P1','P2','P4','P1','P2','P4'],title=f'{n:,} samples')
        axis.grid(axis='y',alpha=.17,zorder=0);axis.set_axisbelow(True)
        axis.text(.5,-.17,f'P4 ratio: cold {cold[-1]["software_to_hardware_ratio"]:.2f}x / resident {resident[-1]["software_to_hardware_ratio"]:.2f}x',
                  transform=axis.transAxes,ha='center',fontsize=9)
    axes[0].set_ylabel('Complete C-call cycles (log scale)')
    fig.suptitle('32-tap FIR: larger blocks amortize accelerator setup',fontsize=17,fontweight='bold')
    fig.legend(handles=[Patch(color=colors[0],label='C reference'),Patch(color=colors[1],label='Cold call (load coefficients)'),
                        Patch(color=colors[4],label='Resident coefficients')],loc='lower center',bbox_to_anchor=(.5,.015),ncol=3,frameon=False)
    fig.text(.5,.095,'Same CPU, compiler flags and initial RAM per block length. Functional RTL cycles; no added DMA wait.',ha='center',fontsize=10)
    files=[]
    for suffix in ['png','svg','pdf']:
        file=destination/('large-block-complete-call.'+suffix);fig.savefig(file,dpi=180,bbox_inches='tight');files.append(file)
    plt.close(fig)
    result={'system_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'plot_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__,
            'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    (destination/'plot-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'plots':[str(f) for f in files]},ensure_ascii=True));return 0


if __name__=='__main__':raise SystemExit(main())
