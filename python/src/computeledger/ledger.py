"""Append-only, hash-chained local ledger of signed receipts, matching
``src/ledger.ts``. Each line of the ledger file is one JSON-encoded
:class:`~computeledger.receipt.SignedReceipt`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .receipt import verify_receipt

LedgerEntry = dict[str, Any]


class Ledger:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def get_last_hash(self) -> str | None:
        entries = self.read_all()
        return None if not entries else entries[-1]["hash"]

    def append(self, entry: LedgerEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self._path.parent, 0o700)
        if not self._path.exists():
            self._path.touch()
            os.chmod(self._path, 0o600)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(self._path, 0o600)

    def read_all(self) -> list[LedgerEntry]:
        if not self._path.exists():
            return []
        raw = self._path.read_text(encoding="utf-8")
        entries: list[LedgerEntry] = []
        for index, line in enumerate(raw.split("\n")):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ledger file is corrupted at line {index + 1}: not valid JSON.") from exc
        return entries

    def get(self, entry_id: str) -> LedgerEntry | None:
        for entry in self.read_all():
            if entry.get("id") == entry_id:
                return entry
        return None


@dataclass
class ChainVerificationResult:
    valid: bool
    entry_count: int
    first_invalid_index: int | None
    first_invalid_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "entryCount": self.entry_count,
            "firstInvalidIndex": self.first_invalid_index,
            "firstInvalidReason": self.first_invalid_reason,
        }


def verify_chain(entries: list[LedgerEntry]) -> ChainVerificationResult:
    """Verifies both each entry's own signature/hash AND that the chain of
    prevHash links is unbroken. An attacker who deletes or reorders a
    historical entry (without also re-signing everything after it, which
    requires the private key) is caught here, not just at the single-receipt
    level."""
    expected_prev_hash: str | None = None
    for i, entry in enumerate(entries):
        result = verify_receipt(entry)
        if not result.valid:
            return ChainVerificationResult(
                valid=False, entry_count=len(entries), first_invalid_index=i,
                first_invalid_reason=result.reason or "unknown",
            )
        if entry.get("prevHash") != expected_prev_hash:
            return ChainVerificationResult(
                valid=False, entry_count=len(entries), first_invalid_index=i,
                first_invalid_reason="chain_broken",
            )
        expected_prev_hash = entry["hash"]
    return ChainVerificationResult(valid=True, entry_count=len(entries), first_invalid_index=None, first_invalid_reason=None)
