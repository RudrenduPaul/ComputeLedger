"""MCP server exposing ComputeLedger's core operations as agent-callable
tools, matching ``src/mcp/server.ts``: ``record_usage``, ``verify_receipt``,
``list_ledger``, ``verify_ledger``.

Uses the official Python MCP SDK (`mcp` on PyPI, the same project as the
TypeScript `@modelcontextprotocol/sdk` used by the TS build). Tools are
registered with flat, per-field parameters (rather than a single wrapped
object) so the generated JSON Schema mirrors the TS server's flat
``recordUsageInputShape``-style schema, keeping the two servers' tool
contracts interoperable for any agent that talks to either.
"""

from __future__ import annotations

import json
from importlib import metadata
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from ..config import resolve_paths
from ..crypto import KeyPairPaths, load_key_pair
from ..ledger import Ledger, verify_chain
from ..receipt import UsageInput, create_receipt, verify_receipt
from .tool_schema import (
    LIST_LEDGER_TOOL_NAME,
    RECORD_USAGE_TOOL_NAME,
    VERIFY_LEDGER_TOOL_NAME,
    VERIFY_RECEIPT_TOOL_NAME,
    DurationSecondsField,
    EstimatedFlopsField,
    GpuHoursField,
    HardwareField,
    LocalField,
    ProviderField,
    ReceiptField,
    WorkloadTypeField,
)


def _package_version() -> str:
    try:
        return metadata.version("computeledger-cli")
    except metadata.PackageNotFoundError:
        return "0.1.0"


PACKAGE_VERSION = _package_version()


def _json_result(data: Any, is_error: bool = False) -> CallToolResult:
    """Wraps a result as a single JSON text block, matching the TS server's
    ``jsonResult`` helper exactly (one text content item holding the pretty-
    printed JSON, rather than the MCP SDK's default of emitting one content
    item per element for list-typed returns)."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))],
        is_error=is_error,
    )


def create_computeledger_mcp_server() -> MCPServer:
    server = MCPServer(name="computeledger-cli", version=PACKAGE_VERSION)

    @server.tool(
        name=RECORD_USAGE_TOOL_NAME,
        title="Record compute usage",
        description=(
            "Records one unit of compute usage (provider, hardware, duration, and optional "
            "GPU-hours/FLOPs/workload type) as a signed, hash-chained receipt in the local "
            "ComputeLedger ledger, and returns that receipt as portable, independently "
            "verifiable proof of the usage claim. Call this after a workload finishes (or with "
            "measured/estimated values) when you need durable evidence of compute consumed, "
            "e.g. reconciling a provider's bill or building a cross-provider audit trail. Do "
            "not call it for read-only lookups (use list_ledger) or to check a receipt you "
            "already have (use verify_receipt). Requires a local Ed25519 keypair generated "
            "beforehand via `computeledger keys generate`; the call fails if none exists.\n\n"
            "Side effects: mutating and NOT idempotent, each call appends a new entry (fresh "
            "UUID and timestamp) to the local ledger file (~/.computeledger by default, or "
            "./.computeledger when local=true) and reads the private key from disk. No network "
            "calls are made. On failure (missing keypair, invalid duration, etc.) it returns "
            "is_error=true with a JSON {\"error\": \"<message>\"} body instead of raising.\n\n"
            "Parameters: provider (str, e.g. 'aws', 'lambda-labs', 'on-prem'), hardware (str, "
            "e.g. 'nvidia-h100', 'nvidia-a100', 'cpu'), durationSeconds (float >= 0), gpuHours "
            "and estimatedFlops (optional float >= 0), workloadType (optional enum: training | "
            "inference | unknown), local (optional bool). Equivalent CLI: `computeledger record "
            "--provider aws --hardware nvidia-h100 --duration-seconds 3600 --gpu-hours 1 "
            "--workload-type training --json`.\n\n"
            "Returns the full signed receipt as JSON: version, id, timestamp (ISO-8601 UTC), "
            "provider, hardware, usage {durationSeconds, gpuHours, estimatedFlops, "
            "gpuUtilizationSamples, workloadType}, command, prevHash, publicKey, hash, and "
            "signature. Pass this object straight into verify_receipt to independently confirm "
            "it."
        ),
    )
    def record_usage(
        provider: ProviderField,
        hardware: HardwareField,
        durationSeconds: DurationSecondsField,
        gpuHours: GpuHoursField = None,
        estimatedFlops: EstimatedFlopsField = None,
        workloadType: WorkloadTypeField = None,
        local: LocalField = None,
    ) -> CallToolResult:
        try:
            paths = resolve_paths(local=bool(local))
            key_pair = load_key_pair(KeyPairPaths(paths.private_key_path, paths.public_key_path))
            ledger = Ledger(paths.ledger_path)
            receipt = create_receipt(
                UsageInput(
                    provider=provider,
                    hardware=hardware,
                    duration_seconds=durationSeconds,
                    gpu_hours=gpuHours,
                    estimated_flops=estimatedFlops,
                    workload_type=workloadType,
                ),
                ledger.get_last_hash(),
                key_pair,
            )
            ledger.append(receipt)
            return _json_result(receipt)
        except Exception as err:  # noqa: BLE001 - tool-level error boundary, matches server.ts's catch
            return _json_result({"error": str(err)}, is_error=True)

    @server.tool(
        name=VERIFY_RECEIPT_TOOL_NAME,
        title="Verify a compute usage receipt",
        description=(
            "Independently checks whether a single signed ComputeLedger receipt is authentic "
            "and untampered, without needing to trust whoever issued it. Call this whenever "
            "you're handed a receipt (from record_usage, `computeledger record`, or a third "
            "party) and need to confirm it's cryptographically valid before trusting the usage "
            "numbers inside it. No prerequisites: it needs nothing on local disk beyond the "
            "receipt object itself, and does not require the signer's private key.\n\n"
            "Side effects: read-only, no ledger writes, no file access beyond the in-memory "
            "argument, no network calls. Fully idempotent, the same receipt always verifies the "
            "same way. It never raises on an invalid receipt, instead it returns a normal "
            "result with is_error=true, so check the 'valid' field rather than relying on an "
            "exception.\n\n"
            "Parameters: receipt (dict) - the full signed receipt object as produced by "
            "record_usage or `computeledger record` (must include version, hash, signature, and "
            "the other receipt fields). Equivalent CLI: `computeledger verify receipt.json "
            "--json`.\n\n"
            "Returns {\"valid\": true} on success, or {\"valid\": false, \"reason\": "
            "\"<invalid_signature|hash_mismatch|unsupported_version|malformed_receipt>\"} on "
            "failure, so callers can distinguish exactly why a receipt failed."
        ),
    )
    def verify_receipt_tool(receipt: ReceiptField) -> CallToolResult:
        result = verify_receipt(receipt)
        return _json_result(result.to_dict(), is_error=not result.valid)

    @server.tool(
        name=LIST_LEDGER_TOOL_NAME,
        title="List ledger entries",
        description=(
            "Lists every signed usage receipt recorded in the local ComputeLedger ledger, in "
            "insertion order. Call this to inspect or export local compute-usage history, e.g. "
            "before running verify_ledger, or to summarize usage across providers. Nothing must "
            "exist beforehand; a missing or empty ledger returns an empty list, not an error.\n\n"
            "Side effects: read-only, reads the local ledger file but never writes to it, makes "
            "no network calls, and is fully idempotent and safe to call repeatedly.\n\n"
            "Parameters: local (optional bool, default false) - true reads "
            "./.computeledger/ledger.jsonl in the current directory instead of "
            "~/.computeledger/ledger.jsonl in the home directory. Equivalent CLI: "
            "`computeledger ledger list --json` (add `--local` to match local=true).\n\n"
            "Returns a JSON array of full signed receipt objects, each with the same shape "
            "record_usage returns (version, id, timestamp, provider, hardware, usage, command, "
            "prevHash, publicKey, hash, signature). Feed any single entry into verify_receipt, "
            "or call verify_ledger to check the whole chain at once."
        ),
    )
    def list_ledger(local: LocalField = None) -> CallToolResult:
        paths = resolve_paths(local=bool(local))
        entries = Ledger(paths.ledger_path).read_all()
        return _json_result(entries)

    @server.tool(
        name=VERIFY_LEDGER_TOOL_NAME,
        title="Verify the full ledger chain",
        description=(
            "Verifies every entry's signature AND the unbroken hash-chain linkage across the "
            "entire local ledger in one call, catching forged receipts as well as deleted, "
            "reordered, or spliced-in entries that a single-receipt check (verify_receipt) "
            "cannot detect on its own. Call this for a full integrity audit of the local ledger "
            "before trusting exported totals, or periodically as a tamper-detection check. "
            "Requires an existing ledger (see list_ledger); an empty ledger verifies as valid "
            "with entryCount 0.\n\n"
            "Side effects: read-only, reads the local ledger file, no writes, no network calls, "
            "fully idempotent. Verification stops at the first invalid entry rather than "
            "continuing past it, since the hash chain is meaningless from that point forward.\n\n"
            "Parameters: local (optional bool, default false) - same meaning as in list_ledger "
            "and record_usage. Equivalent CLI: `computeledger ledger verify --json` (add "
            "`--local` to match local=true).\n\n"
            "Returns {\"valid\": bool, \"entryCount\": <int>, \"firstInvalidIndex\": <int|null>, "
            "\"firstInvalidReason\": \"<invalid_signature|hash_mismatch|unsupported_version|"
            "malformed_receipt|chain_broken|null>\"}. is_error is set to true whenever valid is "
            "false, so a broken chain is visible both in the payload and the MCP error flag."
        ),
    )
    def verify_ledger(local: LocalField = None) -> CallToolResult:
        paths = resolve_paths(local=bool(local))
        entries = Ledger(paths.ledger_path).read_all()
        result = verify_chain(entries)
        return _json_result(result.to_dict(), is_error=not result.valid)

    return server


def run_server() -> None:
    server = create_computeledger_mcp_server()
    server.run(transport="stdio")
