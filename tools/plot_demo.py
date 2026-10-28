"""Render the FIR example and export auditable data (requires Matplotlib)."""

import argparse
import cmath
import csv
import json
import math
from pathlib import Path

from tools.demo_data import make_demo_data

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/step1")
    arguments = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = make_demo_data()
    directory = arguments.output
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.titlesize": 12, "axes.labelsize": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "riscv-fir-step1-v1"})
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), layout="constrained")
    figure.set_facecolor("#FAFAF8")
    for axis in axes:
        axis.set_facecolor("#FAFAF8")
        axis.grid(alpha=0.2)
    figure.suptitle("STEP 1  |  Bit-exact Q15 FIR reference", fontsize=17, fontweight="bold")
    time_ms = [n * 1000 / data["sample_rate_hz"] for n in range(256)]
    axes[0].plot(time_ms, [value / 32768 for value in data["input"][:256]],
                 color="#A3A5AA", linewidth=1, label="Input: 1 kHz + 11 kHz")
    axes[0].plot(time_ms, [value / 32768 for value in data["output"][:256]],
                 color="#006D77", linewidth=1.8, label="Causal 32-tap FIR output")
    axes[0].set(title="Signal example | Fs = 48 kHz, design cutoff = 4 kHz",
                xlabel="Time (ms)", ylabel="Amplitude (full scale)", ylim=(-0.9, 0.9))
    axes[0].legend(loc="upper right")
    axes[0].text(0.01, 0.04, "Zero initial history; linear-phase delay = 15.5 samples",
                 transform=axes[0].transAxes, fontsize=9, color="#555555")

    frequencies = [24000 * index / 1024 for index in range(1025)]
    for coefficients, label, color, style in [
            (data["floating_coefficients"], "Floating design", "#D18533", "--"),
            ([value / 32768 for value in data["coefficients"]], "Q15 coefficients", "#006D77", "-")]:
        response = [20 * math.log10(max(1e-6, abs(sum(
            coefficient * cmath.exp(-2j * math.pi * frequency * k / 48000)
            for k, coefficient in enumerate(coefficients))))) for frequency in frequencies]
        axes[1].plot([frequency / 1000 for frequency in frequencies], response,
                     label=label, color=color, linestyle=style, linewidth=1.4)
    axes[1].axvline(4, color="#777777", linestyle=":", linewidth=1)
    axes[1].set(title="Frequency response | Hamming-windowed sinc, DC normalized before quantization",
                xlabel="Frequency (kHz)", ylabel="Magnitude (dB)", xlim=(0, 24), ylim=(-100, 4))
    axes[1].legend(loc="upper right")
    metrics = data["metrics"]
    axes[1].text(0.02, 0.10,
                 f"Measured 1 kHz gain: {metrics['low_tone_gain_db']:.3f} dB\n"
                 f"Measured 11 kHz rejection: {metrics['high_tone_rejection_db']:.2f} dB",
                 transform=axes[1].transAxes, fontsize=10,
                 bbox={"facecolor": "#FAFAF8", "edgecolor": "none", "alpha": 0.9})

    axes[2].plot(range(160), data["rounding_error_lsb"][:160], color="#5D548E",
                 linewidth=1, marker=".", markersize=3)
    axes[2].axhline(0.5, color="#A35E3B", linestyle="--", linewidth=1)
    axes[2].axhline(-0.5, color="#A35E3B", linestyle="--", linewidth=1)
    axes[2].set(title="Output rounding error | compared with floating FIR using identical quantized operands",
                xlabel="Sample index n", ylabel="Error (output LSB)", ylim=(-0.65, 0.65))
    axes[2].text(0.02, 0.88,
                 f"All {data['sample_count']} samples: max error = "
                 f"{metrics['max_rounding_error_lsb']:.6f} LSB; saturation count = "
                 f"{metrics['saturated_samples']}", transform=axes[2].transAxes, fontsize=9,
                 bbox={"facecolor": "#FAFAF8", "edgecolor": "none", "alpha": 0.95})
    figure.savefig(directory / "fir-reference.png", dpi=180)
    figure.savefig(directory / "fir-reference.svg", metadata={"Date": None})
    plt.close(figure)
    metadata = {key: data[key] for key in ["sample_rate_hz", "sample_count", "cutoff_hz",
                "input_frequencies_hz", "coefficients", "floating_coefficients", "metrics"]}
    metadata["status"] = "Python numerical example; no RTL or hardware measurements"
    (directory / "demo_metrics.json").write_text(json.dumps(metadata, indent=2) + "\n",
                                                 encoding="utf-8", newline="\n")
    with (directory / "demo_samples.csv").open("w", encoding="ascii", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(["n", "input_raw", "output_raw", "float_design", "same_operand_reference",
                         "rounding_error_lsb"])
        writer.writerows(zip(range(data["sample_count"]), data["input"], data["output"],
                             data["float_design"], data["same_operand_reference"],
                             data["rounding_error_lsb"]))
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
