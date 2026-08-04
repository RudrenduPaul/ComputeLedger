"""Mirrors src/receipt.test.ts."""

import pytest

from computeledger.crypto import KeyPairPaths, generate_key_pair
from computeledger.receipt import UsageInput, create_receipt, hash_payload, verify_receipt


@pytest.fixture
def key_pair_factory(tmp_path):
    counter = {"n": 0}

    def make():
        counter["n"] += 1
        d = tmp_path / f"keys-{counter['n']}"
        return generate_key_pair(
            KeyPairPaths(
                private_key_path=str(d / "ed25519.pem"),
                public_key_path=str(d / "ed25519.pub"),
            )
        )

    return make


def test_creates_a_receipt_that_verifies_successfully(key_pair_factory):
    kp = key_pair_factory()
    receipt = create_receipt(
        UsageInput(provider="aws", hardware="nvidia-h100", duration_seconds=120, workload_type="training"),
        None,
        kp,
    )
    result = verify_receipt(receipt)
    assert result.valid is True
    assert result.reason is None


def test_rejects_a_receipt_whose_payload_was_tampered_with_after_signing(key_pair_factory):
    kp = key_pair_factory()
    receipt = create_receipt(
        UsageInput(provider="aws", hardware="nvidia-h100", duration_seconds=120), None, kp
    )
    tampered = dict(receipt)
    tampered["usage"] = {**receipt["usage"], "durationSeconds": 999999}
    result = verify_receipt(tampered)
    assert result.valid is False
    assert result.reason == "hash_mismatch"


def test_rejects_a_receipt_with_a_forged_signature_under_a_substituted_public_key(key_pair_factory):
    kp = key_pair_factory()
    attacker_kp = key_pair_factory()
    receipt = create_receipt(
        UsageInput(provider="aws", hardware="nvidia-h100", duration_seconds=120), None, kp
    )
    # Attacker swaps in their own public key but keeps the original signature —
    # the hash changes because publicKey is part of the signed payload, so this
    # must fail even before signature verification runs.
    forged = dict(receipt)
    forged["publicKey"] = attacker_kp.public_key_raw_base64
    result = verify_receipt(forged)
    assert result.valid is False
    assert result.reason == "hash_mismatch"


def test_rejects_an_unsupported_receipt_version(key_pair_factory):
    kp = key_pair_factory()
    receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), None, kp)
    bad = dict(receipt)
    bad["version"] = "999"
    result = verify_receipt(bad)
    assert result.valid is False
    assert result.reason == "unsupported_version"


def test_chains_prev_hash_across_successive_receipts(key_pair_factory):
    kp = key_pair_factory()
    first = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), None, kp)
    second = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=2), first["hash"], kp)
    assert second["prevHash"] == first["hash"]
    assert hash_payload(first) != hash_payload(second)


def test_rejects_a_forged_signature_bytes_directly(key_pair_factory):
    kp = key_pair_factory()
    receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), None, kp)
    forged = dict(receipt)
    forged["signature"] = receipt["signature"][:-4] + ("AAAA" if receipt["signature"][-4:] != "AAAA" else "BBBB")
    result = verify_receipt(forged)
    assert result.valid is False
    assert result.reason in ("invalid_signature", "malformed_receipt")


def test_default_workload_type_is_unknown(key_pair_factory):
    kp = key_pair_factory()
    receipt = create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=1), None, kp)
    assert receipt["usage"]["workloadType"] == "unknown"
    assert receipt["usage"]["gpuHours"] is None
    assert receipt["usage"]["estimatedFlops"] is None
    assert receipt["command"] is None
    assert receipt["prevHash"] is None


def test_rejects_negative_duration(key_pair_factory):
    kp = key_pair_factory()
    with pytest.raises(ValueError):
        create_receipt(UsageInput(provider="aws", hardware="cpu", duration_seconds=-1), None, kp)
