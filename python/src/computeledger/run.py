"""Executes a wrapped command and measures its wall-clock duration plus any
GPU utilization samples taken while it runs, matching ``src/run.ts``.

Executes the wrapped command via an argv list (never a shell string), so
shell metacharacters in a user-supplied command are inert rather than
re-interpreted. This is the load-bearing security property of
``computeledger run -- <command>``.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field

from .gpu import sample_gpu_once


@dataclass
class RunResult:
    exit_code: int
    duration_seconds: float
    gpu_utilization_samples: list[float] = field(default_factory=list)


def run_and_measure(command: list[str], sample_interval_seconds: float = 2.0) -> RunResult:
    if not command:
        raise ValueError("No command given. Usage: computeledger run -- <command> [args...]")

    samples: list[float] = []
    stop_event = threading.Event()

    def sampler() -> None:
        while not stop_event.wait(sample_interval_seconds):
            try:
                for s in sample_gpu_once():
                    samples.append(s.utilization_percent)
            except Exception:
                pass

    sampler_thread = threading.Thread(target=sampler, daemon=True)

    start = time.perf_counter()
    sampler_thread.start()
    try:
        # stdin/stdout/stderr default to inherited from the parent process
        # (no shell involved: `command` is passed as an argv list).
        proc = subprocess.Popen(command)
        exit_code = proc.wait()
    finally:
        stop_event.set()
        sampler_thread.join(timeout=sample_interval_seconds + 5)
    duration_seconds = time.perf_counter() - start

    return RunResult(
        exit_code=exit_code if exit_code is not None else 1,
        duration_seconds=duration_seconds,
        gpu_utilization_samples=samples,
    )
