"""Path resolution for keys and the local ledger, matching ``src/config.ts``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    private_key_path: str
    public_key_path: str
    ledger_path: str


def resolve_paths(local: bool = False, home: str | None = None, cwd: str | None = None) -> Paths:
    home_dir = home if home is not None else str(Path.home())
    cwd_dir = cwd if cwd is not None else os.getcwd()
    base = Path(cwd_dir, ".computeledger") if local else Path(home_dir, ".computeledger")
    return Paths(
        private_key_path=str(base / "keys" / "ed25519.pem"),
        public_key_path=str(base / "keys" / "ed25519.pub"),
        ledger_path=str(base / "ledger.jsonl"),
    )
