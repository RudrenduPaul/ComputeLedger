"""Mirrors src/mcp/tool-schema.test.ts."""

import pytest
from pydantic import ValidationError

from computeledger.mcp.tool_schema import (
    LIST_LEDGER_TOOL_NAME,
    RECORD_USAGE_TOOL_NAME,
    VERIFY_LEDGER_TOOL_NAME,
    VERIFY_RECEIPT_TOOL_NAME,
    ListLedgerInput,
    RecordUsageInput,
    VerifyLedgerInput,
    VerifyReceiptInput,
)


def test_tool_names_match_the_ts_constants():
    assert RECORD_USAGE_TOOL_NAME == "record_usage"
    assert VERIFY_RECEIPT_TOOL_NAME == "verify_receipt"
    assert LIST_LEDGER_TOOL_NAME == "list_ledger"
    assert VERIFY_LEDGER_TOOL_NAME == "verify_ledger"


def test_record_usage_input_accepts_a_minimal_valid_payload():
    parsed = RecordUsageInput(provider="aws", hardware="nvidia-h100", durationSeconds=30)
    assert parsed.provider == "aws"
    assert parsed.workloadType is None


def test_record_usage_input_rejects_a_negative_duration():
    with pytest.raises(ValidationError):
        RecordUsageInput(provider="aws", hardware="cpu", durationSeconds=-1)


def test_record_usage_input_rejects_a_negative_gpu_hours():
    with pytest.raises(ValidationError):
        RecordUsageInput(provider="aws", hardware="cpu", durationSeconds=1, gpuHours=-1)


def test_record_usage_input_rejects_an_invalid_workload_type_enum_value():
    with pytest.raises(ValidationError):
        RecordUsageInput(provider="aws", hardware="cpu", durationSeconds=1, workloadType="not-a-real-type")


def test_record_usage_input_accepts_all_valid_workload_types():
    for wt in ("training", "inference", "unknown"):
        parsed = RecordUsageInput(provider="aws", hardware="cpu", durationSeconds=1, workloadType=wt)
        assert parsed.workloadType == wt


def test_verify_receipt_input_requires_a_receipt_object():
    with pytest.raises(ValidationError):
        VerifyReceiptInput()
    parsed = VerifyReceiptInput(receipt={"id": "x"})
    assert parsed.receipt == {"id": "x"}


def test_list_and_verify_ledger_input_default_local_to_none():
    assert ListLedgerInput().local is None
    assert VerifyLedgerInput().local is None
    assert ListLedgerInput(local=True).local is True
