"""Direct coverage of computeledger.crypto: keypair generation/loading,
signing, and signature verification (including forged-signature rejection),
plus the canonical-hash helper. Not a 1:1 port of a TS test file (crypto.ts
has no crypto.test.ts on the TS side; its behavior is exercised indirectly
through receipt.test.ts there), but this module is the core cross-language
interop surface so it gets direct tests here.
"""

import base64
import stat

import pytest

from computeledger.crypto import (
    KeyPairPaths,
    generate_key_pair,
    load_key_pair,
    sha256_hex,
    sign_bytes,
    verify_signature,
)


def _paths(tmp_path, name="keys"):
    d = tmp_path / name
    return KeyPairPaths(private_key_path=str(d / "ed25519.pem"), public_key_path=str(d / "ed25519.pub"))


def test_generate_key_pair_writes_files_with_expected_permissions(tmp_path):
    paths = _paths(tmp_path)
    kp = generate_key_pair(paths)

    priv_mode = stat.S_IMODE((tmp_path / "keys" / "ed25519.pem").stat().st_mode)
    pub_mode = stat.S_IMODE((tmp_path / "keys" / "ed25519.pub").stat().st_mode)
    assert priv_mode == 0o600
    assert pub_mode == 0o644

    raw = base64.b64decode(kp.public_key_raw_base64)
    assert len(raw) == 32


def test_load_key_pair_round_trips_generated_keys(tmp_path):
    paths = _paths(tmp_path)
    generated = generate_key_pair(paths)
    loaded = load_key_pair(paths)
    assert loaded.public_key_raw_base64 == generated.public_key_raw_base64
    assert loaded.private_key_pem == generated.private_key_pem


def test_load_key_pair_raises_when_missing(tmp_path):
    paths = _paths(tmp_path, "does-not-exist")
    with pytest.raises(FileNotFoundError):
        load_key_pair(paths)


def test_sign_and_verify_round_trip(tmp_path):
    kp = generate_key_pair(_paths(tmp_path))
    data = b"hello compute ledger"
    signature = sign_bytes(kp.private_key_pem, data)
    assert verify_signature(kp.public_key_raw_base64, data, signature) is True


def test_verify_rejects_signature_from_a_different_key(tmp_path):
    kp_a = generate_key_pair(_paths(tmp_path, "a"))
    kp_b = generate_key_pair(_paths(tmp_path, "b"))
    data = b"payload"
    signature = sign_bytes(kp_a.private_key_pem, data)
    assert verify_signature(kp_b.public_key_raw_base64, data, signature) is False


def test_verify_rejects_tampered_data(tmp_path):
    kp = generate_key_pair(_paths(tmp_path))
    signature = sign_bytes(kp.private_key_pem, b"original")
    assert verify_signature(kp.public_key_raw_base64, b"tampered", signature) is False


def test_verify_rejects_malformed_inputs_without_raising(tmp_path):
    kp = generate_key_pair(_paths(tmp_path))
    assert verify_signature("not-base64!!!", b"data", "also-not-base64!!!") is False
    assert verify_signature(kp.public_key_raw_base64, b"data", "not-a-signature") is False
    assert verify_signature(base64.b64encode(b"too-short").decode(), b"data", "AAAA") is False


def test_sha256_hex_matches_known_vector():
    # sha256("") is a well-known test vector.
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
