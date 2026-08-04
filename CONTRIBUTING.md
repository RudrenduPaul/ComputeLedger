# Contributing to ComputeLedger

ComputeLedger ships two independently maintained implementations of the same receipt format: TypeScript (repo root) and Python (`python/`). A receipt signed by one must verify with the other. Keep that property in mind for any change touching `canonical.ts`/`canonical.py`, `receipt.ts`/`receipt.py`, `crypto.ts`/`crypto.py`, or `ledger.ts`/`ledger.py`.

## Development setup

TypeScript:

```bash
npm install
npm run build
npm test
```

Python:

```bash
cd python
pip install -e ".[dev]"
pytest
```

## Before opening a PR

1. `npm run lint && npm run typecheck && npm run test:coverage` (TypeScript)
2. `pytest` (Python)
3. If you touched the receipt format, canonical JSON serialization, or signing logic, verify cross-language interoperability manually: sign a receipt with one implementation's CLI and verify it with the other's (`computeledger verify <file> --json`). CI runs this automatically, but a local check catches problems faster.

## Reporting bugs

Open a GitHub issue with the CLI command you ran, the output (with `--json` if possible), and your OS/Node/Python version. For security issues, see [SECURITY.md](SECURITY.md) instead of opening a public issue.
