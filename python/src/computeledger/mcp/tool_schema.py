"""MCP tool names and input schemas, matching ``src/mcp/tool-schema.ts``.

The TS side defines its schemas with `zod` (a "raw shape" object registered
directly with the MCP SDK's `McpServer.registerTool`, which the SDK turns
into a flat top-level JSON Schema). This Python port uses `pydantic` (via
`Annotated[..., Field(...)]` type aliases) for the equivalent constraints —
non-negative numbers, workload-type enum, required-vs-optional fields — and
reuses the same aliases both here (for standalone validation, e.g. in
tests) and in ``mcp/server.py`` (as the actual tool function parameter
types), so the two never drift apart.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field

RECORD_USAGE_TOOL_NAME = "record_usage"
VERIFY_RECEIPT_TOOL_NAME = "verify_receipt"
LIST_LEDGER_TOOL_NAME = "list_ledger"
VERIFY_LEDGER_TOOL_NAME = "verify_ledger"

WorkloadTypeLiteral = Literal["training", "inference", "unknown"]

ProviderField = Annotated[
    str, Field(description="Compute provider name, e.g. 'aws', 'lambda-labs', 'on-prem'")
]
HardwareField = Annotated[
    str, Field(description="Hardware identifier, e.g. 'nvidia-h100', 'nvidia-a100', 'cpu'")
]
DurationSecondsField = Annotated[
    float, Field(ge=0, description="Wall-clock duration of the workload in seconds")
]
GpuHoursField = Annotated[
    Optional[float], Field(default=None, ge=0, description="GPU-hours consumed, if known")
]
EstimatedFlopsField = Annotated[
    Optional[float],
    Field(default=None, ge=0, description="Estimated floating point operations, if known"),
]
WorkloadTypeField = Annotated[Optional[WorkloadTypeLiteral], Field(default=None)]
LocalField = Annotated[
    Optional[bool],
    Field(default=None, description="Use the current directory's .computeledger instead of the home directory"),
]
ReceiptField = Annotated[
    dict[str, Any],
    Field(description="A signed ComputeLedger receipt object, as produced by record_usage or `computeledger record`"),
]


class RecordUsageInput(BaseModel):
    """Mirrors ``recordUsageInputShape`` in tool-schema.ts."""

    provider: ProviderField
    hardware: HardwareField
    durationSeconds: DurationSecondsField
    gpuHours: GpuHoursField = None
    estimatedFlops: EstimatedFlopsField = None
    workloadType: WorkloadTypeField = None
    local: LocalField = None


class VerifyReceiptInput(BaseModel):
    """Mirrors ``verifyReceiptInputShape`` in tool-schema.ts."""

    receipt: ReceiptField


class ListLedgerInput(BaseModel):
    """Mirrors ``listLedgerInputShape`` in tool-schema.ts."""

    local: LocalField = None


class VerifyLedgerInput(BaseModel):
    """Mirrors ``verifyLedgerInputShape`` in tool-schema.ts."""

    local: LocalField = None
