"""Derive review tables and optional plots from retained reports; no vendor tools."""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/step22-project-summary'
ART = ROOT / 'artifacts/step22'
INPUTS = {
    'board_simulation': 'reports/step21-board-benchmark/validation.json',
    'large_comparison': 'reports/step20-large-block/comparison.json',
    'parallel_simulation': 'reports/step19-parallel-fir/validation.json',
    'parallel_implementation': 'reports/step19-parallel-fir/implementation-comparison.json',
    'current_implementation': 'reports/step21-board-benchmark/quartus-validation.json',
    'board_feedback': 'reports/step21-board-benchmark/board-observation.json',
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> dict:
    data = {key: json.loads((ROOT / name).read_text(encoding='utf-8'))
            for key, name in INPUTS.items()}
    assert all(data[k]['status'] == 'pass' for k in INPUTS if k != 'board_feedback')
    feedback = data['board_feedback']
    implementation = data['current_implementation']
    assert feedback['user_confirmed_expected_behavior']
    assert feedback['reviewed_sof_sha256'] == implementation['sof_sha256']
    hz = implementation['core_clock_mhz'] * 1_000_000
    baseline = data['board_simulation']['baseline_measurements']
    assert [row['index'] for row in baseline] == list(range(9))
    calls = []
    for index, n in enumerate([64, 256, 1024]):
        sw, cold, resident = [row['cycles'] for row in baseline[index * 3:index * 3 + 3]]
        for mode, cycles in [('hardware_cold', cold), ('hardware_resident', resident)]:
            comparison = [v for v in data['large_comparison']['comparisons']
                          if v['sample_count'] == n and v['lanes'] == 4
                          and v['dma_wait'] == 'none' and v['mode'] == mode]
            assert len(comparison) == 1
            assert comparison[0]['software_cycles'] == sw
            assert comparison[0]['complete_call_cycles'] == cycles
        calls.append(dict(sample_count=n, software_cycles=sw, cold_cycles=cold,
                          resident_cycles=resident, cold_speedup=float(Fraction(sw, cold)),
                          resident_speedup=float(Fraction(sw, resident)),
                          cold_speedup_fraction=str(Fraction(sw, cold)),
                          resident_speedup_fraction=str(Fraction(sw, resident)),
                          software_time_us=sw * 1_000_000 / hz,
                          cold_time_us=cold * 1_000_000 / hz,
                          resident_time_us=resident * 1_000_000 / hz,
                          coefficient_call_difference_cycles=cold-resident,
                          observed_software_cycles=None, observed_cold_cycles=None,
                          observed_resident_cycles=None))
    parallel = []
    for resource in data['parallel_implementation']['available_implementations']:
        lanes = resource['lanes']
        rows = [v for v in data['parallel_simulation']['system']['comparison']
                if v['case'] == 'base' and v['wait_policy'] == 'none' and v['lanes'] == lanes]
        assert len(rows) == 1
        v = rows[0]
        parallel.append(dict(lanes=lanes, sample_count=8,
                             software_cycles=v['software_cycles'],
                             cold_cycles=v['hardware_cold_cycles'],
                             resident_cycles=v['hardware_resident_cycles'],
                             logic_elements=resource['logic_elements'],
                             multiplier_9bit_elements=resource['multiplier_9bit_elements'],
                             setup_slack_ns=resource['worst_setup_slack_ns'],
                             hold_slack_ns=resource['worst_hold_slack_ns']))
    assert [v['lanes'] for v in parallel] == [1, 2, 4]
    return dict(status='pass', clock_hz=hz, taps=32, fir_lanes=4,
                evidence_scope='Functional RTL simulation cycles; actual Quartus resources/timing; general user board acceptance. Numeric board readbacks remain untranscribed.',
                complete_calls=calls, matched_step19_parallel=parallel,
                current_resources=implementation['resources'],
                current_setup_slack_ns=implementation['worst_setup_slack_ns'],
                current_hold_slack_ns=implementation['worst_hold_slack_ns'],
                sof_sha256=implementation['sof_sha256'], board_feedback=feedback['user_quote'],
                physical_numeric_readbacks=feedback['independent_numeric_readback'],
                input_sha256={name: digest(ROOT / name) for name in INPUTS.values()},
                generator_sha256=digest(Path(__file__)))


def write_outputs(summary: dict) -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    for name, rows in [('complete-call-comparison.csv', summary['complete_calls']),
                       ('parallel-lanes-comparison.csv', summary['matched_step19_parallel'])]:
        with (REPORT / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def plot(summary: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    ART.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'svg.fonttype': 'none'})
    colors = ['#263b59', '#087f8c', '#db8736']
    rows = summary['complete_calls']
    x = np.arange(3)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for j, (key, label) in enumerate([('software_cycles', 'CPU software'),
                                     ('cold_cycles', '4-lane cold'),
                                     ('resident_cycles', '4-lane resident')]):
        bars = axes[0].bar(x+(j-1)*.24, [v[key] for v in rows], .23,
                           color=colors[j], label=label)
        axes[0].bar_label(bars, labels=[f'{v[key]:,}' for v in rows], padding=3, fontsize=8)
    axes[0].set(yscale='log', ylim=(400, 1_500_000), xticks=x,
                xticklabels=['64', '256', '1024'], xlabel='Samples per block',
                ylabel='Core cycles (log scale)', title='Complete-call cost at 25 MHz')
    axes[0].legend(frameon=False, loc='upper left')
    for key, label, color in [('cold_speedup', 'Cold: coefficients included', colors[1]),
                               ('resident_speedup', 'Resident: preload outside interval', colors[2])]:
        ys = [v[key] for v in rows]
        axes[1].plot(x, ys, 'o-', lw=2.2, color=color, label=label)
        for a, b in zip(x, ys):
            offset = -15 if key == 'cold_speedup' else 9
            axes[1].annotate(f'{b:.2f}x', (a, b), xytext=(0, offset),
                             textcoords='offset points', ha='center', color=color)
    axes[1].set(xticks=x, xticklabels=['64', '256', '1024'], ylim=(15, 43),
                xlabel='Samples per block', ylabel='Software / hardware call cycles',
                title='Derived cycle ratio')
    axes[1].legend(frameon=False, loc='lower right', fontsize=8)
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis='y', color='#e3e7eb', linewidth=.7)
    fig.suptitle('32-tap Q15 FIR | same CPU, memory, data and rounding', fontsize=13)
    fig.supxlabel('Functional simulation counts. User reports matching board behavior; individual numeric readbacks pending.', fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(ART / f'complete-call-comparison.{ext}', dpi=180)
    plt.close(fig)

    rows = summary['matched_step19_parallel']
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout='constrained')
    for j, (key, label, color) in enumerate([('cold_cycles', 'Cold call', colors[1]),
                                           ('resident_cycles', 'Resident call', colors[2])]):
        bars = axes[0].bar(x+(j-.5)*.29, [v[key] for v in rows], .28,
                           color=color, label=label)
        axes[0].bar_label(bars, padding=3)
    axes[0].set(xticks=x, xticklabels=['1', '2', '4'], ylim=(0, 700),
                xlabel='FIR MAC lanes', ylabel='Complete-call cycles',
                title='Matched step19 workload: 8 samples')
    axes[0].legend(frameon=False)
    bars = axes[1].bar(x, [v['multiplier_9bit_elements'] for v in rows], .55, color=colors[0])
    axes[1].bar_label(bars, padding=4)
    axes[1].set(xticks=x, xticklabels=[f"{v['lanes']} lanes\n{v['logic_elements']:,} LE" for v in rows],
                ylim=(0, 18), ylabel='9-bit multiplier elements (whole SoC)',
                title='Actual Quartus resource counts')
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis='y', color='#e3e7eb', linewidth=.7)
    fig.suptitle('Controlled lane comparison | identical step19 sources, 25 MHz target', fontsize=12)
    fig.supxlabel('Left: functional simulation. Right: user Quartus builds. These are separate from the step21 resource configuration.', fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(ART / f'parallel-lanes-comparison.{ext}', dpi=180)
    plt.close(fig)
    provenance = {'data_sha256': digest(REPORT / 'summary.json'),
                  'matplotlib_version': matplotlib.__version__,
                  'files': {p.name: digest(p) for p in sorted(ART.glob('*')) if p.suffix in {'.png', '.svg'}}}
    (ART / 'plot-provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plots', action='store_true', help='Optional Matplotlib/NumPy figures')
    args = parser.parse_args()
    summary = derive()
    write_outputs(summary)
    if args.plots:
        plot(summary)
    print(json.dumps({'status': summary['status'], 'lengths': [v['sample_count'] for v in summary['complete_calls']],
                      'cold_speedups': [v['cold_speedup'] for v in summary['complete_calls']],
                      'resident_speedups': [v['resident_speedup'] for v in summary['complete_calls']],
                      'numeric_board_readbacks': summary['physical_numeric_readbacks'], 'plots': args.plots}))


if __name__ == '__main__':
    main()
