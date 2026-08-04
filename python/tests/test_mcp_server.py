"""Behavioral coverage of the MCP server: tool registration and end-to-end
tool calls against a real local keystore/ledger (via the same MCPServer
instance a `computeledger mcp` process would run).
"""

import asyncio
import json

import pytest

from computeledger.crypto import KeyPairPaths, generate_key_pair
from computeledger.mcp.server import create_computeledger_mcp_server
from computeledger.mcp.tool_schema import (
    LIST_LEDGER_TOOL_NAME,
    RECORD_USAGE_TOOL_NAME,
    VERIFY_LEDGER_TOOL_NAME,
    VERIFY_RECEIPT_TOOL_NAME,
)


def _extract_json(call_tool_result):
    text = call_tool_result.content[0].text
    return json.loads(text)


@pytest.fixture
def local_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generate_key_pair(
        KeyPairPaths(
            private_key_path=str(tmp_path / ".computeledger" / "keys" / "ed25519.pem"),
            public_key_path=str(tmp_path / ".computeledger" / "keys" / "ed25519.pub"),
        )
    )
    return tmp_path


def test_server_registers_all_four_tools():
    server = create_computeledger_mcp_server()

    async def _list():
        return await server.list_tools()

    tools = asyncio.run(_list())
    names = {t.name for t in tools}
    assert names == {
        RECORD_USAGE_TOOL_NAME,
        VERIFY_RECEIPT_TOOL_NAME,
        LIST_LEDGER_TOOL_NAME,
        VERIFY_LEDGER_TOOL_NAME,
    }


def test_record_usage_then_verify_and_list_via_tools(local_keys):
    server = create_computeledger_mcp_server()

    async def _run():
        record_result = await server.call_tool(
            RECORD_USAGE_TOOL_NAME,
            {"provider": "aws", "hardware": "nvidia-h100", "durationSeconds": 42.0, "local": True},
        )
        receipt = _extract_json(record_result)
        assert receipt["provider"] == "aws"
        assert record_result.is_error is False

        verify_result = await server.call_tool(VERIFY_RECEIPT_TOOL_NAME, {"receipt": receipt})
        verified = _extract_json(verify_result)
        assert verified["valid"] is True
        assert verify_result.is_error is False

        list_result = await server.call_tool(LIST_LEDGER_TOOL_NAME, {"local": True})
        entries = _extract_json(list_result)
        assert len(entries) == 1
        assert entries[0]["id"] == receipt["id"]

        chain_result = await server.call_tool(VERIFY_LEDGER_TOOL_NAME, {"local": True})
        chain = _extract_json(chain_result)
        assert chain["valid"] is True
        assert chain["entryCount"] == 1

    asyncio.run(_run())


def test_verify_receipt_tool_reports_invalid_for_tampered_receipt(local_keys):
    server = create_computeledger_mcp_server()

    async def _run():
        record_result = await server.call_tool(
            RECORD_USAGE_TOOL_NAME,
            {"provider": "aws", "hardware": "cpu", "durationSeconds": 1.0, "local": True},
        )
        receipt = _extract_json(record_result)
        receipt["usage"]["durationSeconds"] = 999999

        verify_result = await server.call_tool(VERIFY_RECEIPT_TOOL_NAME, {"receipt": receipt})
        verified = _extract_json(verify_result)
        assert verified["valid"] is False
        assert verified["reason"] == "hash_mismatch"
        assert verify_result.is_error is True

    asyncio.run(_run())


def test_record_usage_tool_rejects_negative_duration_at_the_schema_level(local_keys):
    server = create_computeledger_mcp_server()

    async def _run():
        with pytest.raises(Exception):
            await server.call_tool(
                RECORD_USAGE_TOOL_NAME,
                {"provider": "aws", "hardware": "cpu", "durationSeconds": -5},
            )

    asyncio.run(_run())
