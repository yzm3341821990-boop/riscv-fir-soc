# Changelog

## Step22 — pipeline CPU and parallel FIR

- Added a five-stage CPU with forwarding, load-use stalls and control-flow flushes, preserving the implemented 37-RV32I-plus-MUL subset.
- Added matched 1/2/4-lane FIR configurations and archived user Quartus resource/timing reports.
- Expanded shared data memory to 32 KiB true-dual-port M9K and exercised 64/256/1024-sample C workloads.
- Added a nine-profile board sequencer and accepted-marker cycle timer, with independent stopwatch, reset and controlled-fault verification.
- Recorded general user board acceptance; retained individual numeric readbacks and video as missing evidence.
- Added data-derived result tables/plots, current architecture/quickstart and release review material. Preserved historical entry points.

This commit publishes the approved step22 review snapshot. No release tag is created. Physical programming and Quartus compilation remain user operations; no new license was selected.

## v0.1 — published source

Initial multi-cycle CPU, Q15 FIR MMIO system and DE2-115 display demonstration. Published commit: 75b34a2269f7f33e99fa38d10d37d7824fdc1cf7.
