"""Mirrors src/ledger.test.ts."""

import pytest

from computeledger.crypto import KeyPairPaths, generate_key_pair
from computeledger.ledger import Ledger, verify_chain
from computeledger.receipt import UsageInput, create_receipt


def _key_pair(tmp_path):
    return generate_key_pair(
        KeyPairPaths(
            private_key_path=str(tmp_path / "keys" / "ed25519.pem"),
            public_key_path=str(tmp_path / "keys" / "ed25519.pub"),
        )
    )


def test_appends_entries_and_reads_them_back_in_order(tmp_path):
    kp = _key_pair(tmp_path)
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    r1 = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), ledger.get_last_hash(), kp)
    ledger.append(r1)
    r2 = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=2), ledger.get_last_hash(), kp)
    ledger.append(r2)

    all_entries = ledger.read_all()
    assert [e["id"] for e in all_entries] == [r1["id"], r2["id"]]


def test_verifies_a_valid_unbroken_chain(tmp_path):
    kp = _key_pair(tmp_path)
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    for i in range(5):
        receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=i), ledger.get_last_hash(), kp)
        ledger.append(receipt)
    result = verify_chain(ledger.read_all())
    assert result.valid is True
    assert result.entry_count == 5
    assert result.first_invalid_index is None
    assert result.first_invalid_reason is None


def test_detects_a_deleted_middle_entry_chain_broken(tmp_path):
    kp = _key_pair(tmp_path)
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    entries = []
    for i in range(3):
        receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=i), ledger.get_last_hash(), kp)
        ledger.append(receipt)
        entries.append(receipt)

    spliced = [entries[0], entries[2]]
    result = verify_chain(spliced)
    assert result.valid is False
    assert result.first_invalid_reason == "chain_broken"
    assert result.first_invalid_index == 1


def test_detects_a_tampered_historical_entry_even_if_chain_links_look_intact(tmp_path):
    kp = _key_pair(tmp_path)
    receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=10), None, kp)
    tampered = dict(receipt)
    tampered["usage"] = {**receipt["usage"], "durationSeconds": 10000}
    result = verify_chain([tampered])
    assert result.valid is False
    assert result.first_invalid_reason == "hash_mismatch"


def test_get_returns_entry_by_id(tmp_path):
    kp = _key_pair(tmp_path)
    ledger = Ledger(str(tmp_path / "ledger.jsonl"))
    r1 = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), None, kp)
    ledger.append(r1)
    assert ledger.get(r1["id"])["id"] == r1["id"]
    assert ledger.get("does-not-exist") is None


def test_read_all_on_missing_file_returns_empty_list(tmp_path):
    ledger = Ledger(str(tmp_path / "nonexistent" / "ledger.jsonl"))
    assert ledger.read_all() == []
    assert ledger.get_last_hash() is None


def test_raises_a_clear_error_instead_of_an_uncaught_crash_on_a_corrupted_ledger_line(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text("not valid json\n", encoding="utf-8")
    ledger = Ledger(str(ledger_path))
    with pytest.raises(ValueError, match="corrupted at line 1"):
        ledger.read_all()
