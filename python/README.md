# computeledger-cli (Python)

Python port of [ComputeLedger](https://github.com/RudrenduPaul/ComputeLedger): a provider-agnostic
CLI for recording compute usage (GPU-hours, hardware type, duration, workload type) as a
cryptographically signed, hash-chained receipt, plus a `verify` command so any third party can
check a receipt's authenticity without trusting the issuer.

This package is byte-for-byte interoperable with the TypeScript `computeledger-cli` package
published from the same repository: a receipt signed by one implementation verifies as valid in
the other. Both serialize the signed payload with the same canonical JSON rules (sorted keys, no
whitespace, matching numeric formatting) before hashing with SHA-256 and signing with Ed25519, so
the on-disk/on-wire receipt format is language-agnostic by design.

See the [main repository README](https://github.com/RudrenduPaul/ComputeLedger) for the full
project overview, design rationale, and usage guide.

## Install

```bash
pip install computeledger-cli
```

## Quick start

```bash
computeledger keys generate
computeledger record --provider aws --hardware nvidia-h100 --duration-seconds 3600 --gpu-hours 1 --json
computeledger verify receipt.json --json
computeledger ledger verify
```

## Commands

```
computeledger keys generate [--local]
computeledger keys show [--local] [--json]
computeledger run [--local] [--provider <name>] [--hardware <type>] [--workload-type training|inference|unknown] [--no-record-command] [--json] -- <command...>
computeledger record --provider <name> --hardware <type> --duration-seconds <n> [--gpu-hours <n>] [--flops <n>] [--workload-type <type>] [--local] [--json]
computeledger verify <receipt.json> [--json]
computeledger ledger list [--local] [--json]
computeledger ledger show <id> [--local] [--json]
computeledger ledger verify [--local] [--json]
computeledger export --format json|csv [--out <file>] [--local]
computeledger mcp
```

`--local` uses `./.computeledger` in the current directory instead of `~/.computeledger`.
`--json` produces structured JSON output on stdout, suitable for agent/programmatic use.

## MCP server

`computeledger mcp` starts a Model Context Protocol server (stdio transport) exposing
`record_usage`, `verify_receipt`, `list_ledger`, and `verify_ledger` as agent-callable tools,
built on the official Python MCP SDK (`mcp` on PyPI).

## Cryptography

Ed25519 signing and verification use the [`cryptography`](https://pypi.org/project/cryptography/)
package. Public keys are stored and transmitted as base64 of the raw 32-byte Ed25519 public key
(not PEM, not SPKI-wrapped), matching the TypeScript implementation's on-disk format exactly.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0
