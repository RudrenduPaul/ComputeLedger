"""Ed25519 signing/verification and SHA-256 hashing, byte- and
key-format-compatible with the TypeScript implementation (``src/crypto.ts``).

Uses the ``cryptography`` package's Ed25519 primitives — the standard,
well-vetted choice for this operation in Python (unlike Node, Python's
standard library has no built-in asymmetric crypto, so a real dependency is
required here; this is the one place this port takes on a dependency the TS
side didn't need).

Interop contract:
  * Public keys are stored/transmitted as base64 of the RAW 32-byte Ed25519
    public key — never PEM, never SPKI-DER-wrapped. The TS side derives this
    raw form by exporting SPKI DER and slicing off the fixed 12-byte OID
    prefix; the ``cryptography`` package exposes the raw form directly via
    ``Encoding.Raw`` / ``PublicFormat.Raw``, so no manual slicing is needed
    here, but the resulting bytes (and therefore the base64 string) are
    identical either way.
  * Signatures are base64 of the raw 64-byte Ed25519 signature over the raw
    bytes of the hex-decoded receipt hash (never over the hash's hex text).
  * Private keys are stored as PKCS8 PEM on disk, matching Node's
    ``export({ type: "pkcs8", format: "pem" })`` output format.
"""

from __future__ import annotations

import base64
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

RAW_PUBLIC_KEY_LENGTH = 32


@dataclass(frozen=True)
class KeyPairPaths:
    private_key_path: str
    public_key_path: str


@dataclass(frozen=True)
class LoadedKeyPair:
    private_key_pem: str
    public_key_raw_base64: str


def generate_key_pair(paths: KeyPairPaths) -> LoadedKeyPair:
    """Generates a new Ed25519 keypair and writes it to disk with the same
    permission model as the TS side: private key directory 0700, private
    key file 0600, public key file 0644."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    public_key_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_raw_base64 = base64.b64encode(public_key_raw).decode("ascii")

    priv_path = Path(paths.private_key_path)
    pub_path = Path(paths.public_key_path)

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(priv_path.parent, 0o700)

    priv_path.write_text(private_key_pem, encoding="utf-8")
    os.chmod(priv_path, 0o600)

    pub_path.write_text(public_key_raw_base64, encoding="utf-8")
    os.chmod(pub_path, 0o644)

    return LoadedKeyPair(private_key_pem=private_key_pem, public_key_raw_base64=public_key_raw_base64)


def load_key_pair(paths: KeyPairPaths) -> LoadedKeyPair:
    priv_path = Path(paths.private_key_path)
    pub_path = Path(paths.public_key_path)
    if not priv_path.exists() or not pub_path.exists():
        raise FileNotFoundError(
            f'No signing key found at {paths.private_key_path}. Run "computeledger keys generate" first.'
        )
    private_key_pem = priv_path.read_text(encoding="utf-8")
    public_key_raw_base64 = pub_path.read_text(encoding="utf-8").strip()
    return LoadedKeyPair(private_key_pem=private_key_pem, public_key_raw_base64=public_key_raw_base64)


def sign_bytes(private_key_pem: str, data: bytes) -> str:
    private_key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Private key is not an Ed25519 key")
    signature = private_key.sign(bytes(data))
    return base64.b64encode(signature).decode("ascii")


def verify_signature(public_key_raw_base64: str, data: bytes, signature_base64: str) -> bool:
    try:
        raw_key = base64.b64decode(public_key_raw_base64, validate=True)
        if len(raw_key) != RAW_PUBLIC_KEY_LENGTH:
            return False
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
        signature = base64.b64decode(signature_base64, validate=True)
        public_key.verify(signature, bytes(data))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()
