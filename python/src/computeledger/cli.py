"""Command-line interface, matching ``src/cli.ts``'s subcommands and flags.

This hand-rolls its own tiny argument parser rather than depending on
``argparse`` or ``click``. That mirrors the TypeScript CLI's own choice
(see the comment in ``crypto.ts`` about Ed25519 support): a smaller
dependency surface is a deliberate security property for a signing tool,
and this CLI's actual surface (a handful of subcommands, each with a
handful of ``--flag value`` pairs plus one ``--`` passthrough case for
``run``) doesn't need a framework's generality. ``argparse`` in particular
does not model the ``computeledger run [flags] -- <command...>`` shape
(where everything after ``--`` is opaque passthrough to a child process)
as directly as splitting on the first literal ``--`` token does here.
"""

from __future__ import annotations

import json
import math
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence

from .config import resolve_paths
from .crypto import KeyPairPaths, generate_key_pair, load_key_pair
from .ledger import Ledger, verify_chain
from .output import print_error, print_result
from .receipt import UsageInput, WorkloadType, create_receipt, verify_receipt
from .run import run_and_measure


def _version() -> str:
    try:
        return metadata.version("computeledger-cli")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def _has_flag(args: Sequence[str], name: str) -> bool:
    return name in args


def _get_option(args: Sequence[str], name: str) -> str | None:
    try:
        idx = args.index(name)
    except ValueError:
        return None
    if idx == len(args) - 1:
        return None
    return args[idx + 1]


def _split_on_double_dash(args: Sequence[str]) -> tuple[list[str], list[str]]:
    if "--" in args:
        idx = args.index("--")
        return list(args[:idx]), list(args[idx + 1 :])
    return list(args), []


def _parse_workload_type(raw: str | None) -> WorkloadType:
    if raw in ("training", "inference", "unknown"):
        return raw  # type: ignore[return-value]
    return "unknown"


def _key_paths(local: bool) -> KeyPairPaths:
    paths = resolve_paths(local=local)
    return KeyPairPaths(private_key_path=paths.private_key_path, public_key_path=paths.public_key_path)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else None
    rest = args[1:]
    json_output = _has_flag(rest, "--json") or _has_flag(args, "--json")

    try:
        if command is None or command in ("--help", "-h"):
            _print_help()
            return 0
        if command in ("--version", "-v"):
            sys.stdout.write(f"{_version()}\n")
            return 0
        if command == "keys":
            return _handle_keys(rest, json_output)
        if command == "run":
            return _handle_run(rest, json_output)
        if command == "record":
            return _handle_record(rest, json_output)
        if command == "verify":
            return _handle_verify(rest, json_output)
        if command == "ledger":
            return _handle_ledger(rest, json_output)
        if command == "export":
            return _handle_export(rest, json_output)
        if command == "mcp":
            return _handle_mcp()
        print_error(f'Unknown command "{command}". Run "computeledger --help".', json_output)
        return 1
    except Exception as err:  # noqa: BLE001 - CLI top-level error boundary, matches cli.ts's catch
        print_error(str(err), json_output)
        return 1


def _print_help() -> None:
    version = _version()
    sys.stdout.write(
        f"""computeledger v{version}

Provider-agnostic CLI for signing, hash-chaining, and verifying compute usage receipts.

Usage:
  computeledger keys generate [--local]
  computeledger keys show [--local] [--json]
  computeledger run [--local] [--provider <name>] [--hardware <type>] [--workload-type training|inference|unknown] [--no-record-command] [--json] -- <command...>
  computeledger record --provider <name> --hardware <type> --duration-seconds <n> [--gpu-hours <n>] [--flops <n>] [--workload-type <type>] [--local] [--json]
  computeledger verify <receipt.json> [--json]
  computeledger ledger list [--local] [--json]
  computeledger ledger show <id> [--local] [--json]
  computeledger ledger verify [--local] [--json]
  computeledger export --format json|csv [--out <file>] [--local]
  computeledger mcp

Flags:
  --local   Use ./.computeledger in the current directory instead of ~/.computeledger
  --json    Structured JSON output on stdout, suitable for agent/programmatic use
"""
    )


def _handle_keys(rest: list[str], json_output: bool) -> int:
    sub = rest[0] if rest else None
    flags = rest[1:]
    local = _has_flag(flags, "--local")
    key_paths = _key_paths(local)

    if sub == "generate":
        key_pair = generate_key_pair(key_paths)
        print_result(
            {
                "publicKey": key_pair.public_key_raw_base64,
                "privateKeyPath": key_paths.private_key_path,
                "publicKeyPath": key_paths.public_key_path,
            },
            f"Generated Ed25519 keypair.\nPublic key: {key_pair.public_key_raw_base64}\n"
            f"Private key: {key_paths.private_key_path} (mode 600)",
            json_output,
        )
        return 0
    if sub == "show":
        key_pair = load_key_pair(key_paths)
        print_result({"publicKey": key_pair.public_key_raw_base64}, key_pair.public_key_raw_base64, json_output)
        return 0
    print_error(f'Unknown "keys" subcommand "{sub}". Use "generate" or "show".', json_output)
    return 1


def _handle_run(rest: list[str], json_output: bool) -> int:
    flags, command = _split_on_double_dash(rest)
    if not command:
        print_error("Usage: computeledger run [flags] -- <command> [args...]", json_output)
        return 1

    local = _has_flag(flags, "--local")
    provider = _get_option(flags, "--provider") or "unknown"
    hardware = _get_option(flags, "--hardware") or "unknown"
    workload_type = _parse_workload_type(_get_option(flags, "--workload-type"))
    record_command = not _has_flag(flags, "--no-record-command")

    paths = resolve_paths(local=local)
    key_pair = load_key_pair(KeyPairPaths(paths.private_key_path, paths.public_key_path))
    ledger = Ledger(paths.ledger_path)

    result = run_and_measure(command)

    receipt = create_receipt(
        UsageInput(
            provider=provider,
            hardware=hardware,
            duration_seconds=result.duration_seconds,
            gpu_hours=(result.duration_seconds / 3600) if result.gpu_utilization_samples else None,
            gpu_utilization_samples=result.gpu_utilization_samples or None,
            workload_type=workload_type,
            command=" ".join(command) if record_command else None,
        ),
        ledger.get_last_hash(),
        key_pair,
    )
    ledger.append(receipt)

    print_result(
        receipt,
        f"Job exited {result.exit_code}. Recorded usage receipt {receipt['id']} "
        f"({result.duration_seconds:.2f}s, {len(result.gpu_utilization_samples)} GPU samples).",
        json_output,
    )
    return result.exit_code


def _handle_record(rest: list[str], json_output: bool) -> int:
    local = _has_flag(rest, "--local")
    provider = _get_option(rest, "--provider")
    hardware = _get_option(rest, "--hardware")
    duration_raw = _get_option(rest, "--duration-seconds")
    gpu_hours_raw = _get_option(rest, "--gpu-hours")
    flops_raw = _get_option(rest, "--flops")
    workload_type = _parse_workload_type(_get_option(rest, "--workload-type"))

    if not provider or not hardware or duration_raw is None:
        print_error(
            "Usage: computeledger record --provider <name> --hardware <type> --duration-seconds <n> "
            "[--gpu-hours <n>] [--flops <n>] [--workload-type <type>]",
            json_output,
        )
        return 1

    try:
        duration_seconds = float(duration_raw)
    except ValueError:
        duration_seconds = float("nan")
    if not math.isfinite(duration_seconds) or duration_seconds < 0:
        print_error("--duration-seconds must be a non-negative number", json_output)
        return 1

    gpu_hours: float | None = None
    if gpu_hours_raw is not None:
        try:
            gpu_hours = float(gpu_hours_raw)
        except ValueError:
            gpu_hours = float("nan")
        if not math.isfinite(gpu_hours) or gpu_hours < 0:
            print_error("--gpu-hours must be a non-negative number", json_output)
            return 1

    estimated_flops: float | None = None
    if flops_raw is not None:
        try:
            estimated_flops = float(flops_raw)
        except ValueError:
            estimated_flops = float("nan")
        if not math.isfinite(estimated_flops) or estimated_flops < 0:
            print_error("--flops must be a non-negative number", json_output)
            return 1

    paths = resolve_paths(local=local)
    key_pair = load_key_pair(KeyPairPaths(paths.private_key_path, paths.public_key_path))
    ledger = Ledger(paths.ledger_path)

    receipt = create_receipt(
        UsageInput(
            provider=provider,
            hardware=hardware,
            duration_seconds=duration_seconds,
            gpu_hours=gpu_hours,
            estimated_flops=estimated_flops,
            workload_type=workload_type,
        ),
        ledger.get_last_hash(),
        key_pair,
    )
    ledger.append(receipt)

    print_result(receipt, f"Recorded usage receipt {receipt['id']}.", json_output)
    return 0


def _handle_verify(rest: list[str], json_output: bool) -> int:
    file_path = next((a for a in rest if not a.startswith("--")), None)
    if not file_path:
        print_error("Usage: computeledger verify <receipt.json>", json_output)
        return 1
    path = Path(file_path)
    if not path.exists():
        print_error(f"File not found: {file_path}", json_output)
        return 1
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print_error(f"File is not valid JSON: {file_path}", json_output)
        return 1

    result = verify_receipt(receipt)
    print_result(
        result.to_dict(),
        "Receipt is valid: signature and hash match." if result.valid else f"Receipt is INVALID: {result.reason}",
        json_output,
    )
    return 0 if result.valid else 1


def _handle_ledger(rest: list[str], json_output: bool) -> int:
    sub = rest[0] if rest else None
    flags = rest[1:]
    local = _has_flag(flags, "--local") or _has_flag(rest, "--local")
    paths = resolve_paths(local=local)
    ledger = Ledger(paths.ledger_path)

    if sub == "list":
        entries = ledger.read_all()
        human = "\n".join(
            f"{e['id']}  {e['timestamp']}  {e['provider']}/{e['hardware']}  {e['usage']['durationSeconds']:.1f}s"
            for e in entries
        ) or "(empty ledger)"
        print_result(entries, human, json_output)
        return 0
    if sub == "show":
        entry_id = next((a for a in flags if not a.startswith("--")), None)
        if not entry_id:
            print_error("Usage: computeledger ledger show <id>", json_output)
            return 1
        entry = ledger.get(entry_id)
        if not entry:
            print_error(f"No ledger entry with id {entry_id}", json_output)
            return 1
        print_result(entry, json.dumps(entry, indent=2, ensure_ascii=False), json_output)
        return 0
    if sub == "verify":
        result = verify_chain(ledger.read_all())
        print_result(
            result.to_dict(),
            f"Ledger valid: {result.entry_count} entries, unbroken hash chain."
            if result.valid
            else f"Ledger INVALID at entry {result.first_invalid_index}: {result.first_invalid_reason}",
            json_output,
        )
        return 0 if result.valid else 1
    print_error(f'Unknown "ledger" subcommand "{sub}". Use "list", "show", or "verify".', json_output)
    return 1


def _handle_export(rest: list[str], json_output: bool) -> int:
    local = _has_flag(rest, "--local")
    fmt = _get_option(rest, "--format") or "json"
    out_path = _get_option(rest, "--out")
    paths = resolve_paths(local=local)
    entries = Ledger(paths.ledger_path).read_all()

    if fmt == "csv":
        header = "id,timestamp,provider,hardware,durationSeconds,gpuHours,workloadType"
        rows = [
            f"{e['id']},{e['timestamp']},{e['provider']},{e['hardware']},"
            f"{e['usage']['durationSeconds']},{e['usage'].get('gpuHours') if e['usage'].get('gpuHours') is not None else ''},"
            f"{e['usage']['workloadType']}"
            for e in entries
        ]
        output = "\n".join([header, *rows])
    else:
        output = json.dumps(entries, indent=2, ensure_ascii=False)

    if out_path:
        Path(out_path).write_text(output, encoding="utf-8")
        print_result({"written": out_path, "count": len(entries)}, f"Exported {len(entries)} entries to {out_path}", json_output)
    else:
        sys.stdout.write(output + "\n")
    return 0


def _handle_mcp() -> int:
    from .mcp.server import run_server

    run_server()
    return 0


def run() -> None:
    """Console-script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    run()
