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
            "Records a compute usage entry, signs it with the local Ed25519 key, appends it to "
            "the hash-chained local ledger, and returns the signed receipt."
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
            "Independently verifies a signed ComputeLedger receipt's cryptographic signature and "
            "hash integrity, without needing to trust the issuer."
        ),
    )
    def verify_receipt_tool(receipt: ReceiptField) -> CallToolResult:
        result = verify_receipt(receipt)
        return _json_result(result.to_dict(), is_error=not result.valid)

    @server.tool(
        name=LIST_LEDGER_TOOL_NAME,
        title="List ledger entries",
        description="Lists every usage receipt recorded in the local ComputeLedger ledger.",
    )
    def list_ledger(local: LocalField = None) -> CallToolResult:
        paths = resolve_paths(local=bool(local))
        entries = Ledger(paths.ledger_path).read_all()
        return _json_result(entries)

    @server.tool(
        name=VERIFY_LEDGER_TOOL_NAME,
        title="Verify the full ledger chain",
        description=(
            "Verifies every entry's signature plus the unbroken hash chain across the entire "
            "local ledger, detecting tampering, deletion, or reordering."
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
