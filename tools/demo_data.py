"""A deterministic 48-kHz, two-tone FIR example; standard library only."""

import math

from model.fixed_fir import fir_block, quantize_q15, round_shift


def _lowpass_coefficients():
    taps, cutoff, sample_rate = 32, 4000, 48000
    values = []
    for index in range(taps):
        offset = index - (taps - 1) / 2
        ideal = math.sin(2 * math.pi * cutoff / sample_rate * offset) / (math.pi * offset)
        window = 0.54 - 0.46 * math.cos(2 * math.pi * index / (taps - 1))
        values.append(ideal * window)
    dc_gain = sum(values)
    return [value / dc_gain for value in values]


def _float_filter(samples, coefficients):
    return [sum(coefficient * samples[n - k]
                for k, coefficient in enumerate(coefficients) if k <= n)
            for n in range(len(samples))]


def _tone_amplitude(samples, frequency, sample_rate, start):
    # The last 3072 samples contain integer periods of both example tones.
    count = len(samples) - start
    sine = sum(samples[n] * math.sin(2 * math.pi * frequency * n / sample_rate)
               for n in range(start, len(samples)))
    cosine = sum(samples[n] * math.cos(2 * math.pi * frequency * n / sample_rate)
                 for n in range(start, len(samples)))
    return 2 * math.hypot(sine, cosine) / count


def make_demo_data() -> dict:
    sample_rate, count, measurement_start = 48000, 4096, 1024
    floating_coefficients = _lowpass_coefficients()
    coefficients = [quantize_q15(value) for value in floating_coefficients]
    # 12 kHz is an accidental exact zero of these quantized coefficients.
    # 11 kHz gives a measurable stopband tone rather than numerical cancellation.
    floating_input = [0.45 * math.sin(2 * math.pi * 1000 * n / sample_rate)
                      + 0.35 * math.sin(2 * math.pi * 11000 * n / sample_rate)
                      for n in range(count)]
    samples = [quantize_q15(value) for value in floating_input]
    result = fir_block(samples, coefficients)
    input_values = [value / 32768 for value in samples]
    output_values = [value / 32768 for value in result.outputs]
    float_design = _float_filter(floating_input, floating_coefficients)
    same_operands = _float_filter(input_values, [value / 32768 for value in coefficients])
    rounding_error_lsb = [(actual - reference) * 32768
                          for actual, reference in zip(output_values, same_operands)]
    design_errors = [actual - reference for actual, reference in zip(output_values, float_design)]
    amplitudes = {}
    for frequency in (1000, 11000):
        amplitudes[frequency] = (
            _tone_amplitude(input_values, frequency, sample_rate, measurement_start),
            _tone_amplitude(output_values, frequency, sample_rate, measurement_start))
    low_input, low_output = amplitudes[1000]
    high_input, high_output = amplitudes[11000]
    metrics = {
        "max_rounding_error_lsb": max(map(abs, rounding_error_lsb)),
        "max_abs_error_vs_float_design": max(map(abs, design_errors)),
        "rmse_vs_float_design": math.sqrt(sum(error * error for error in design_errors) / count),
        "saturated_samples": sum(not -32768 <= round_shift(value) <= 32767
                                 for value in result.accumulators),
        "low_tone_gain_db": 20 * math.log10(low_output / low_input),
        "high_tone_rejection_db": 20 * math.log10(high_input / high_output),
        "coefficient_integer_sum": sum(coefficients),
        "measurement_start_sample": measurement_start,
        "measurement_samples": count - measurement_start,
    }
    return {"sample_rate_hz": sample_rate, "sample_count": count, "cutoff_hz": 4000,
            "input_frequencies_hz": [1000, 11000], "input": samples,
            "output": list(result.outputs), "coefficients": coefficients,
            "floating_coefficients": floating_coefficients,
            "floating_input": floating_input, "float_design": float_design,
            "same_operand_reference": same_operands,
            "rounding_error_lsb": rounding_error_lsb, "metrics": metrics}
