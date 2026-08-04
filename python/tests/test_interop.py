"""Cross-language interoperability tests: a receipt signed by this Python
CLI must verify as valid under the TypeScript CLI, and vice versa. This is
the core value proposition of ComputeLedger (see the module docstring in
computeledger/canonical.py) so it is tested directly here, not just
asserted by code review.

Skipped automatically if the TypeScript build (``dist/cli.js`` at the repo
root) or a `node` binary isn't available in the environment running the
test -- this keeps `pytest` runnable in isolation (e.g. a pure-Python CI
job that never builds the TS side) while still giving real, non-mocked
coverage wherever both toolchains are present.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_CLI = REPO_ROOT / "dist" / "cli.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    NODE is None or not TS_CLI.exists(),
    reason="requires a built TS CLI (npm run build) and a node binary on PATH",
)


def run_py_cli(args, cwd):
    proc = subprocess.run(
        [sys.executable, "-m", "computeledger.cli", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=30,
    )
    return proc.stdout, proc.returncode


def run_ts_cli(args, cwd):
    proc = subprocess.run(
        [NODE, str(TS_CLI), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=30,
    )
    return proc.stdout, proc.returncode


def test_python_signed_receipt_verifies_under_the_ts_cli(tmp_path):
    run_py_cli(["keys", "generate", "--local"], tmp_path)
    stdout, status = run_py_cli(
        ["record", "--local", "--provider", "aws", "--hardware", "nvidia-h100",
         "--duration-seconds", "3600", "--gpu-hours", "1", "--json"],
        tmp_path,
    )
    assert status == 0
    receipt_path = tmp_path / "py-signed.json"
    receipt_path.write_text(stdout)

    ts_stdout, ts_status = run_ts_cli(["verify", str(receipt_path), "--json"], tmp_path)
    assert ts_status == 0, ts_stdout
    assert json.loads(ts_stdout)["valid"] is True


def test_ts_signed_receipt_verifies_under_the_python_cli(tmp_path):
    run_ts_cli(["keys", "generate", "--local"], tmp_path)
    ts_stdout, ts_status = run_ts_cli(
        ["record", "--local", "--provider", "lambda-labs", "--hardware", "nvidia-a100",
         "--duration-seconds", "1800", "--flops", "1e18", "--json"],
        tmp_path,
    )
    assert ts_status == 0
    receipt_path = tmp_path / "ts-signed.json"
    receipt_path.write_text(ts_stdout)

    py_stdout, py_status = run_py_cli(["verify", str(receipt_path), "--json"], tmp_path)
    assert py_status == 0, py_stdout
    assert json.loads(py_stdout)["valid"] is True
