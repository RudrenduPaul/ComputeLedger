"""Receipt creation and verification, matching ``src/receipt.ts`` field-for-
field. This is the core of the cross-language interop contract: the exact
set of fields hashed, their types, and the hashing/signing procedure must
match the TypeScript implementation exactly, or a receipt signed in one
language will fail to verify in the other.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from .canonical import canonicalize_to_bytes
from .crypto import LoadedKeyPair, sha256_hex, sign_bytes, verify_signature

RECEIPT_VERSION = "1"

WorkloadType = Literal["training", "inference", "unknown"]
_VALID_WORKLOAD_TYPES = ("training", "inference", "unknown")


@dataclass
class UsageInput:
    provider: str
    hardware: str
    duration_seconds: float
    gpu_hours: float | None = None
    estimated_flops: float | None = None
    gpu_utilization_samples: list[float] | None = None
    workload_type: WorkloadType | None = None
    command: str | None = None


class UsagePayload(TypedDict):
    durationSeconds: float
    gpuHours: float | None
    estimatedFlops: float | None
    gpuUtilizationSamples: list[float] | None
    workloadType: str


class ReceiptPayload(TypedDict):
    version: str
    id: str
    timestamp: str
    provider: str
    hardware: str
    usage: UsagePayload
    command: str | None
    prevHash: str | None
    publicKey: str


class SignedReceipt(ReceiptPayload):
    hash: str
    signature: str


def _iso_now() -> str:
    """Millisecond-precision ISO-8601 UTC timestamp with a literal 'Z'
    suffix, matching JavaScript's ``new Date().toISOString()`` exactly
    (Python's own ``datetime.isoformat()`` defaults to microsecond
    precision and a '+00:00' offset instead)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _build_payload(usage_input: UsageInput, prev_hash: str | None, public_key: str) -> ReceiptPayload:
    if usage_input.duration_seconds < 0:
        raise ValueError("durationSeconds must be >= 0")
    workload_type = usage_input.workload_type or "unknown"
    if workload_type not in _VALID_WORKLOAD_TYPES:
        raise ValueError(f"Invalid workloadType: {workload_type!r}")
    return {
        "version": RECEIPT_VERSION,
        "id": str(uuid.uuid4()),
        "timestamp": _iso_now(),
        "provider": usage_input.provider,
        "hardware": usage_input.hardware,
        "usage": {
            "durationSeconds": usage_input.duration_seconds,
            "gpuHours": usage_input.gpu_hours,
            "estimatedFlops": usage_input.estimated_flops,
            "gpuUtilizationSamples": usage_input.gpu_utilization_samples,
            "workloadType": workload_type,
        },
        "command": usage_input.command,
        "prevHash": prev_hash,
        "publicKey": public_key,
    }


def hash_payload(payload: dict[str, Any]) -> str:
    """The hash covers every field an attacker could tamper with, including
    publicKey and prevHash — binding the signer's identity and chain
    position into the signed digest is what stops a receipt being replayed
    under a different key or spliced into a different position in the
    chain."""
    return sha256_hex(canonicalize_to_bytes(payload))


def create_receipt(usage_input: UsageInput, prev_hash: str | None, key_pair: LoadedKeyPair) -> SignedReceipt:
    payload = _build_payload(usage_input, prev_hash, key_pair.public_key_raw_base64)
    digest_hex = hash_payload(payload)
    signature = sign_bytes(key_pair.private_key_pem, bytes.fromhex(digest_hex))
    receipt: SignedReceipt = {**payload, "hash": digest_hex, "signature": signature}  # type: ignore[typeddict-item]
    return receipt


VerifyFailureReason = Literal["invalid_signature", "hash_mismatch", "unsupported_version", "malformed_receipt"]


@dataclass
class VerifyResult:
    valid: bool
    reason: VerifyFailureReason | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"valid": self.valid}
        if self.reason is not None:
            out["reason"] = self.reason
        return out


def verify_receipt(receipt: Any) -> VerifyResult:
    if not isinstance(receipt, dict):
        return VerifyResult(valid=False, reason="malformed_receipt")
    if receipt.get("version") != RECEIPT_VERSION:
        return VerifyResult(valid=False, reason="unsupported_version")

    payload = {k: v for k, v in receipt.items() if k not in ("hash", "signature")}

    try:
        recomputed_hash = hash_payload(payload)
    except (TypeError, ValueError):
        return VerifyResult(valid=False, reason="malformed_receipt")

    if recomputed_hash != receipt.get("hash"):
        return VerifyResult(valid=False, reason="hash_mismatch")

    try:
        sig_valid = verify_signature(
            payload.get("publicKey", ""), bytes.fromhex(receipt["hash"]), receipt.get("signature", "")
        )
    except (TypeError, ValueError):
        return VerifyResult(valid=False, reason="malformed_receipt")

    if not sig_valid:
        return VerifyResult(valid=False, reason="invalid_signature")

    return VerifyResult(valid=True)
