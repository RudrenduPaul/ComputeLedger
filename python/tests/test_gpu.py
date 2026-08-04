"""Mirrors src/gpu.test.ts.

These run against whatever `nvidia-smi` actually resolves to on the test
machine (usually absent in CI/dev). The point of the test is that neither
function throws or hangs when it's missing -- a common case, not an error.
"""

from computeledger.gpu import is_gpu_available, sample_gpu_once


def test_is_gpu_available_resolves_to_a_bool_without_throwing():
    available = is_gpu_available()
    assert isinstance(available, bool)


def test_sample_gpu_once_resolves_to_a_list_without_throwing():
    samples = sample_gpu_once()
    assert isinstance(samples, list)
