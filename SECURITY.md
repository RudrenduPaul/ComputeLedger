# Security Policy

## Reporting a vulnerability

Please report security issues privately via [GitHub Security Advisories](https://github.com/RudrenduPaul/ComputeLedger/security/advisories/new) rather than a public issue. Include a description of the issue, steps to reproduce, and the affected version.

## Scope

ComputeLedger's security model is entirely local: signing keys, the ledger, and all writes stay on the machine running the CLI. There is no server component, no account system, and no network calls other than what the `mcp` subcommand's stdio transport requires from whatever MCP client invokes it.

Relevant areas for a security report:

- Signature forgery or verification bypass (`src/receipt.ts`, `src/crypto.ts`, `python/src/computeledger/receipt.py`, `python/src/computeledger/crypto.py`)
- Hash-chain tampering that `ledger verify` fails to detect (`src/ledger.ts`, `python/src/computeledger/ledger.py`)
- Command injection via `computeledger run` (`src/run.ts`, `python/src/computeledger/run.py`)
- Key storage or file-permission issues (`src/crypto.ts`, `python/src/computeledger/crypto.py`)
- Cross-language interoperability bugs that make a legitimately signed receipt fail verification in the other implementation, or an invalid receipt pass

## Supported versions

Only the latest published release on npm and PyPI receives security fixes.
