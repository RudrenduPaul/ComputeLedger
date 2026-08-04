"""computeledger: provider-agnostic recording, hash-chaining, and
verification of cryptographically signed compute usage receipts.

Python port of the ComputeLedger TypeScript implementation
(https://github.com/RudrenduPaul/ComputeLedger). Receipts produced or
verified by this package are byte-for-byte interoperable with the
TypeScript CLI: a receipt signed by one implementation verifies as valid
in the other, because both serialize the signed payload with the same
canonical JSON rules before hashing (see :mod:`computeledger.canonical`).
"""

from __future__ import annotations

from .canonical import canonicalize, canonicalize_to_bytes
from .config import Paths, resolve_paths
from .crypto import (
    KeyPairPaths,
    LoadedKeyPair,
    generate_key_pair,
    load_key_pair,
    sha256_hex,
    sign_bytes,
    verify_signature,
)
from .ledger import ChainVerificationResult, Ledger, verify_chain
from .receipt import (
    RECEIPT_VERSION,
    ReceiptPayload,
    SignedReceipt,
    UsageInput,
    VerifyResult,
    WorkloadType,
    create_receipt,
    hash_payload,
    verify_receipt,
)

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("computeledger-cli")
except Exception:  # pragma: no cover - package not installed (e.g. running from source)
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "canonicalize",
    "canonicalize_to_bytes",
    "Paths",
    "resolve_paths",
    "KeyPairPaths",
    "LoadedKeyPair",
    "generate_key_pair",
    "load_key_pair",
    "sha256_hex",
    "sign_bytes",
    "verify_signature",
    "ChainVerificationResult",
    "Ledger",
    "verify_chain",
    "RECEIPT_VERSION",
    "ReceiptPayload",
    "SignedReceipt",
    "UsageInput",
    "VerifyResult",
    "WorkloadType",
    "create_receipt",
    "hash_payload",
    "verify_receipt",
]
