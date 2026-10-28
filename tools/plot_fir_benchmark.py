"""Render the audited Step 14 cycle comparison, using optional Matplotlib."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[1]
CASE_LABELS = {
    'base': 'Base mix',
    'base_impulse': 'Impulse',
    'base_ties': 'Half-LSB ties',
    'base_positive_extreme': 'Positive extreme',
    'base_negative_extreme': 'Negative extreme',
    'base_zero': 'Zero input',
    'base_zero_coefficients': 'Zero coefficients',
}
SERIES = (
    ('software_cycles', 'software', 'Software FIR', '#344F70'),
    ('hardware_cold_cycles', 'hardware_cold', 'Hardware: cold call', '#D88A2D'),
    ('hardware_resident_cycles', 'hardware_resident', 'Hardware: coefficients resident', '#168A80'),
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_name(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def load_results(comparison_path, measurements_path):
    """Reject duplicates, incomplete comparisons and mismatched raw measurements."""
    rows = json.loads(Path(comparison_path).read_text(encoding='utf-8'))
    measurements = json.loads(Path(measurements_path).read_text(encoding='utf-8'))
    lookup = {}
    raw = {}
    for record in measurements:
        key = (record['wait_policy'], record['case'], record['mode'])
        if key in raw:
            raise ValueError('duplicate raw measurement: '+str(key))
        raw[key] = record
    for row in rows:
        key = (row['wait_policy'], row['case'])
        if key in lookup:
            raise ValueError('duplicate comparison row: '+str(key))
        lookup[key] = row
        for field, mode, _, _ in SERIES:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError('cycles must be positive integers')
            measured = raw.get((*key, mode))
            if measured is None or measured['cycles'] != value:
                raise ValueError('comparison differs from raw measurement: '+str((*key, mode)))
        for field, denominator in [('cold_cycle_ratio', 'hardware_cold_cycles'),
                                   ('resident_cycle_ratio', 'hardware_resident_cycles')]:
            if not math.isclose(row[field], row['software_cycles']/row[denominator], rel_tol=1e-12):
                raise ValueError('cycle ratio differs from underlying cycle counts')
    expected = {(policy, case) for policy in ('none', 'periodic') for case in CASE_LABELS}
    if set(lookup) != expected:
        raise ValueError('expected all seven datasets under both DMA wait policies')
    return rows, lookup


def render(comparison_path, measurements_path, output):
    rows, results = load_results(comparison_path, measurements_path)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.titlesize': 11, 'axes.labelsize': 10,
        'xtick.labelsize': 9, 'ytick.labelsize': 10,
        'axes.spines.top': False, 'axes.spines.right': False,
        'svg.hashsalt': 'riscv-fir-step14-cycle-comparison-v1', 'svg.fonttype': 'none',
    })
    figure = plt.figure(figsize=(12.8, 7.6), facecolor='white')
    axis = figure.add_axes([0.17, 0.22, 0.57, 0.56])
    kernel_axis = figure.add_axes([0.81, 0.48, 0.16, 0.30])
    figure.text(0.17, 0.94, 'FIR software / hardware: measured clock cycles',
                fontsize=17, fontweight='bold', ha='left')
    figure.text(0.17, 0.90, 'Same CPU and RAM layout  |  32 taps, 8 signed-Q15 samples  |  Lower is better',
                fontsize=10.5, color='#4F5660', ha='left')

    names = list(CASE_LABELS)
    positions = list(range(len(names)))
    offsets = (-0.235, 0, 0.235)
    handles = []
    for index, (field, _, label, color) in enumerate(SERIES):
        values = [results[('none', name)][field] for name in names]
        bars = axis.barh([p+offsets[index] for p in positions], values, height=0.21,
                         color=color, label=label, edgecolor='white', linewidth=0.35,
                         hatch='///' if index == 2 else None, zorder=3)
        handles.append(bars)
        for bar, value in zip(bars, values):
            axis.text(value+28, bar.get_y()+bar.get_height()/2, str(value),
                      va='center', ha='left', fontsize=8.5, color='#26303B')
    axis.set_yticks(positions, [CASE_LABELS[name] for name in names])
    axis.invert_yaxis()
    maximum = max(results[('none', name)]['software_cycles'] for name in names)
    axis.set_xlim(0, math.ceil((maximum+150)/500)*500)
    axis.xaxis.set_major_locator(MultipleLocator(500))
    axis.set_xlabel('Full invocation (clock cycles)', labelpad=9)
    axis.set_title('A  Complete invocation, no injected DMA waits', loc='left', pad=15,
                   fontweight='bold')
    axis.grid(axis='x', color='#DCE1E6', linewidth=0.7, zorder=0)
    axis.set_axisbelow(True)
    axis.spines['left'].set_visible(False)
    axis.spines['bottom'].set_color('#88939E')
    axis.tick_params(axis='y', length=0, pad=12)
    figure.legend(handles, [s[2] for s in SERIES], loc='center', bbox_to_anchor=(0.57, 0.845),
                  ncol=3, frameon=False, fontsize=9.5, handlelength=1.7, columnspacing=2.0)

    kernel_values = [results[(policy, 'base')]['cold_kernel_cycles'] for policy in ('none', 'periodic')]
    bars = kernel_axis.bar([0, 1], kernel_values, width=0.58,
                          color=['#8799AF', '#B45A4F'], edgecolor='white', linewidth=0.6, zorder=3)
    kernel_axis.set_xticks([0, 1], ['No wait', 'Periodic'])
    kernel_axis.set_ylim(0, math.ceil((max(kernel_values)+25)/50)*50)
    kernel_axis.yaxis.set_major_locator(MultipleLocator(100))
    kernel_axis.set_ylabel('Task clock cycles', labelpad=6)
    kernel_axis.set_title('B  Accelerator task only\nCold call, base input', loc='left', pad=15,
                          fontweight='bold', fontsize=10.5)
    kernel_axis.grid(axis='y', color='#DCE1E6', linewidth=0.7, zorder=0)
    kernel_axis.spines['left'].set_color('#88939E')
    kernel_axis.spines['bottom'].set_color('#88939E')
    for bar, value in zip(bars, kernel_values):
        kernel_axis.text(bar.get_x()+bar.get_width()/2, value+6, str(value),
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

    base = results[('none', 'base')]
    figure.text(0.81, 0.385, 'Base-input cycle ratios', fontsize=10, fontweight='bold')
    figure.text(0.81, 0.345, f"Software / cold: {base['cold_cycle_ratio']:.2f}x", fontsize=10)
    figure.text(0.81, 0.310, f"Software / resident: {base['resident_cycle_ratio']:.2f}x", fontsize=10)
    figure.text(0.81, 0.240, 'Resident preload is outside\nthe timed call.', fontsize=8.8,
                color='#4F5660', linespacing=1.6)

    identical = all(results[('none', name)][field] == results[('periodic', name)][field]
                    for name in names for field, *_ in SERIES)
    if identical:
        wait_note = ('The periodic DMA wait policy gives the same full-call totals here; '
                     'task cycles rise from '+str(kernel_values[0])+' to '+str(kernel_values[1])+'.')
    else:
        wait_note = 'Panel A shows no-wait full calls; panel B separately shows the periodic-wait effect on the base task.'
    notes = [
        'Cold calls include all 32 coefficient writes, configuration, START, polling and return; resident calls exclude coefficient preload.',
        wait_note,
        'Accepted marker-store interval; common result validation is outside it. Functional simulation only: physical timing and resources are unmeasured.',
    ]
    for y, text in zip((0.13, 0.095, 0.06), notes):
        figure.text(0.17, y, text, fontsize=8.3, color='#4F5660', ha='left')

    png = output/'fir-cycle-comparison.png'
    svg = output/'fir-cycle-comparison.svg'
    figure.savefig(png, dpi=300, facecolor='white', metadata={'Software': 'Matplotlib '+matplotlib.__version__})
    figure.savefig(svg, facecolor='white', metadata={'Date': None, 'Creator': 'tools/plot_fir_benchmark.py'})
    plt.close(figure)
    provenance = {
        'status': 'rendered', 'chart': 'audited full-invocation and accelerator-task clock cycles',
        'scope': 'ModelSim functional simulation; no physical latency, Fmax or FPGA resource claims',
        'inputs': {source_name(path): digest(path) for path in (comparison_path, measurements_path)},
        'source_sha256': {source_name(__file__): digest(__file__)},
        'artifacts_sha256': {p.name: digest(p) for p in (png, svg)},
        'python_version': platform.python_version(), 'matplotlib_version': matplotlib.__version__,
        'backend': 'Agg', 'figure_size_inches': [12.8, 7.6], 'png_dpi': 300,
        'datasets': names, 'comparison_rows': len(rows),
        'primary_panel_wait_policy': 'none', 'periodic_full_calls_identical': identical,
        'base_input': base, 'base_accelerator_task_cycles': dict(zip(('none', 'periodic'), kernel_values)),
        'rendering_note': 'Existing Matplotlib runtime used; no packages installed or network accessed',
    }
    metadata = output/'plot-provenance.json'
    metadata.write_text(json.dumps(provenance, indent=2, sort_keys=True)+'\n', encoding='utf-8', newline='\n')
    return {'png': str(png.resolve()), 'svg': str(svg.resolve()), 'provenance': str(metadata.resolve()),
            'matplotlib_version': matplotlib.__version__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, default=ROOT/'reports/step14-fir-benchmark/comparison.json')
    parser.add_argument('--measurements', type=Path, default=ROOT/'reports/step14-fir-benchmark/measurements.json')
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/step14')
    args = parser.parse_args()
    print(json.dumps(render(args.comparison, args.measurements, args.output), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__': raise SystemExit(main())
