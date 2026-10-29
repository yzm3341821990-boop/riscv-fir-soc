"""Plot actual accepted-marker intervals; optional Matplotlib dependency only."""
import argparse
import csv
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('reports/step19-parallel-fir/comparison.csv'))
    p.add_argument('--output',type=Path,default=Path('artifacts/step19'))
    a=p.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=list(csv.DictReader(a.input.open(encoding='utf-8')))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),sharey=True)
    fig.subplots_adjust(left=.08,right=.985,top=.77,bottom=.18,wspace=.10)
    colors=['#8795A3','#3465A4','#168C82']
    for ax,wait,title in zip(axes,['none','periodic'],['No added DMA wait','Periodic DMA wait']):
        selected=sorted((r for r in rows if r['case']=='base' and r['wait_policy']==wait),key=lambda r:int(r['lanes']))
        if [int(r['lanes']) for r in selected]!=[1,2,4]:raise ValueError('missing base comparison')
        for offset,key,label,color in zip([-.25,0,.25],
            ['software_cycles','hardware_cold_cycles','hardware_resident_cycles'],
            ['Software FIR','Hardware: cold call','Hardware: coefficients resident'],colors):
            values=[int(r[key]) for r in selected]
            bars=ax.bar([n+offset for n in range(3)],values,width=.23,label=label,color=color,zorder=3)
            ax.bar_label(bars,padding=4,fontsize=9)
        ax.set_xticks(range(3),['1 MAC lane','2 MAC lanes','4 MAC lanes'])
        ax.set_title(title,pad=13,fontweight='bold')
        ax.set_ylim(0,900);ax.grid(axis='y',color='#DCE3E9',linewidth=.6,zorder=0)
    axes[0].set_ylabel('Complete-call clock cycles (lower is better)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.93),ncol=3,frameon=False,fontsize=10)
    fig.suptitle('Parallel FIR on the same five-stage RISC-V CPU',fontsize=16,fontweight='bold',y=.99)
    fig.text(.5,.035,'32 taps, N=8, identical firmware and input. Functional simulation; new implementation timing pending.',ha='center',fontsize=9)
    a.output.mkdir(parents=True,exist_ok=True)
    for suffix in ['png','svg','pdf']:
        file=a.output/('parallel-fir-complete-call.'+suffix)
        fig.savefig(file,dpi=180,metadata={'Creator':'RISC-V FIR SoC measured-cycle plot'})
        print(file)
    plt.close(fig);return 0


if __name__=='__main__':raise SystemExit(main())
