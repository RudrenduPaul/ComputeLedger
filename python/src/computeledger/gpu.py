"""Best-effort GPU utilization sampling via ``nvidia-smi``, matching
``src/gpu.ts``. Never raises: a machine with no NVIDIA GPU (most CI
runners, most laptops) is the common case, not an error case, so absence of
``nvidia-smi`` degrades to an empty sample list rather than failing the
whole ``run`` command.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class GpuSample:
    utilization_percent: float
    memory_used_mib: float


def sample_gpu_once() -> list[GpuSample]:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []

    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    samples: list[GpuSample] = []
    for line in proc.stdout.strip().split("\n"):
        parts = line.split(",")
        if len(parts) != 2:
            continue
        try:
            util = float(parts[0].strip())
            mem = float(parts[1].strip())
        except ValueError:
            continue
        samples.append(GpuSample(utilization_percent=util, memory_used_mib=mem))
    return samples


def is_gpu_available() -> bool:
    try:
        proc = subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=10)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0
