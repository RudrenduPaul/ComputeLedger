import { homedir } from "node:os";
import { join } from "node:path";

export interface Paths {
  privateKeyPath: string;
  publicKeyPath: string;
  ledgerPath: string;
}

export function resolvePaths(opts: { local?: boolean; home?: string; cwd?: string } = {}): Paths {
  const home = opts.home ?? homedir();
  const cwd = opts.cwd ?? process.cwd();
  const base = opts.local ? join(cwd, ".computeledger") : join(home, ".computeledger");
  return {
    privateKeyPath: join(base, "keys", "ed25519.pem"),
    publicKeyPath: join(base, "keys", "ed25519.pub"),
    ledgerPath: join(base, "ledger.jsonl")
  };
}
