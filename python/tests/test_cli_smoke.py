"""Mirrors src/cli.smoke.test.ts: end-to-end tests against the real CLI
entry point via subprocess, using an argv list (never shell=True/string
interpolation)."""

import json
import subprocess
import sys

import pytest


def run_cli(args, cwd):
    proc = subprocess.run(
        [sys.executable, "-m", "computeledger.cli", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout, proc.returncode


def run_cli_full(args, cwd):
    proc = subprocess.run(
        [sys.executable, "-m", "computeledger.cli", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout, proc.stderr, proc.returncode


def test_prints_help_with_no_arguments(tmp_path):
    stdout, status = run_cli([], tmp_path)
    assert "computeledger" in stdout
    assert status == 0


def test_generates_keys_records_usage_and_verifies_the_receipt_round_trip(tmp_path):
    _, status = run_cli(["keys", "generate", "--local"], tmp_path)
    assert status == 0
    assert (tmp_path / ".computeledger" / "keys" / "ed25519.pem").exists()

    stdout, status = run_cli(
        ["record", "--local", "--provider", "aws", "--hardware", "nvidia-h100", "--duration-seconds", "60", "--json"],
        tmp_path,
    )
    assert status == 0
    receipt = json.loads(stdout)
    assert receipt["provider"] == "aws"

    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(stdout)
    stdout, status = run_cli(["verify", str(receipt_path), "--json"], tmp_path)
    assert status == 0
    assert json.loads(stdout)["valid"] is True


def test_rejects_a_tampered_receipt_on_verify(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    stdout, _ = run_cli(
        ["record", "--local", "--provider", "aws", "--hardware", "cpu", "--duration-seconds", "5", "--json"],
        tmp_path,
    )
    receipt = json.loads(stdout)
    receipt["usage"]["durationSeconds"] = 99999
    receipt_path = tmp_path / "tampered.json"
    receipt_path.write_text(json.dumps(receipt))

    stdout, status = run_cli(["verify", str(receipt_path), "--json"], tmp_path)
    assert status == 1
    assert json.loads(stdout)["valid"] is False


def test_chains_multiple_ledger_entries_and_passes_ledger_verify(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    run_cli(["record", "--local", "--provider", "aws", "--hardware", "cpu", "--duration-seconds", "1"], tmp_path)
    run_cli(["record", "--local", "--provider", "aws", "--hardware", "cpu", "--duration-seconds", "2"], tmp_path)

    stdout, _ = run_cli(["ledger", "list", "--local", "--json"], tmp_path)
    entries = json.loads(stdout)
    assert len(entries) == 2
    assert entries[1]["prevHash"] == entries[0]["hash"]

    stdout, status = run_cli(["ledger", "verify", "--local", "--json"], tmp_path)
    assert status == 0
    assert json.loads(stdout)["valid"] is True


def test_rejects_a_malformed_command_with_a_non_zero_exit_code_not_a_crash(tmp_path):
    _, status = run_cli(["not-a-real-command"], tmp_path)
    assert status == 1


def test_rejects_a_non_numeric_gpu_hours_with_a_clean_error_not_a_raw_traceback(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    _, stderr, status = run_cli_full(
        ["record", "--local", "--provider", "aws", "--hardware", "cpu", "--duration-seconds", "1", "--gpu-hours", "not-a-number", "--json"],
        tmp_path,
    )
    assert status == 1
    assert "--gpu-hours must be a non-negative number" in stderr
    assert "Traceback" not in stderr


def test_keys_show_prints_the_public_key_generated_by_keys_generate(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    stdout, status = run_cli(["keys", "show", "--local", "--json"], tmp_path)
    assert status == 0
    public_key = json.loads(stdout)["publicKey"]
    import re

    assert re.match(r"^[A-Za-z0-9+/]+=*$", public_key)


def test_run_wraps_a_real_command_measures_duration_and_appends_a_receipt(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    stdout, status = run_cli(
        ["run", "--local", "--provider", "on-prem", "--hardware", "cpu", "--json", "--", sys.executable, "-c", "1+1"],
        tmp_path,
    )
    assert status == 0
    receipt = json.loads(stdout)
    assert receipt["provider"] == "on-prem"
    assert receipt["command"] == f"{sys.executable} -c 1+1"
    assert receipt["usage"]["durationSeconds"] >= 0


def test_run_no_record_command_omits_the_command_text_from_the_receipt(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    stdout, _ = run_cli(
        [
            "run", "--local", "--provider", "on-prem", "--hardware", "cpu",
            "--no-record-command", "--json", "--", sys.executable, "-c", "1",
        ],
        tmp_path,
    )
    receipt = json.loads(stdout)
    assert receipt["command"] is None


def test_run_propagates_the_wrapped_commands_non_zero_exit_code(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    _, status = run_cli(
        ["run", "--local", "--provider", "aws", "--hardware", "cpu", "--", sys.executable, "-c", "import sys; sys.exit(7)"],
        tmp_path,
    )
    assert status == 7


def test_export_writes_json_and_csv_ledger_dumps_to_a_file(tmp_path):
    run_cli(["keys", "generate", "--local"], tmp_path)
    run_cli(["record", "--local", "--provider", "aws", "--hardware", "cpu", "--duration-seconds", "1"], tmp_path)

    json_out = tmp_path / "out.json"
    _, status = run_cli(["export", "--local", "--format", "json", "--out", str(json_out)], tmp_path)
    assert status == 0
    assert json_out.exists()
    assert len(json.loads(json_out.read_text())) == 1

    csv_out = tmp_path / "out.csv"
    _, status = run_cli(["export", "--local", "--format", "csv", "--out", str(csv_out)], tmp_path)
    assert status == 0
    assert "id,timestamp,provider,hardware" in csv_out.read_text()
