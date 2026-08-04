"""Mirrors src/config.test.ts."""

from computeledger.config import resolve_paths


def test_defaults_to_the_home_directory():
    paths = resolve_paths(home="/home/user", cwd="/repo")
    assert paths.private_key_path == "/home/user/.computeledger/keys/ed25519.pem"
    assert paths.ledger_path == "/home/user/.computeledger/ledger.jsonl"


def test_uses_the_current_directory_when_local_is_true():
    paths = resolve_paths(local=True, home="/home/user", cwd="/repo")
    assert paths.private_key_path == "/repo/.computeledger/keys/ed25519.pem"
    assert paths.ledger_path == "/repo/.computeledger/ledger.jsonl"
