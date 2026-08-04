import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { SignedReceipt } from "./receipt.js";
import { verifyReceipt } from "./receipt.js";

export type LedgerEntry = SignedReceipt;

export class Ledger {
  constructor(private readonly path: string) {}

  getLastHash(): string | null {
    const entries = this.readAll();
    return entries.length === 0 ? null : entries[entries.length - 1].hash;
  }

  append(entry: LedgerEntry): void {
    mkdirSync(dirname(this.path), { recursive: true, mode: 0o700 });
    if (!existsSync(this.path)) {
      writeFileSync(this.path, "", { mode: 0o600 });
    }
    appendFileSync(this.path, `${JSON.stringify(entry)}\n`, { mode: 0o600 });
  }

  readAll(): LedgerEntry[] {
    if (!existsSync(this.path)) return [];
    const raw = readFileSync(this.path, "utf8");
    return raw
      .split("\n")
      .filter((line) => line.trim().length > 0)
      .map((line, index) => {
        try {
          return JSON.parse(line) as LedgerEntry;
        } catch {
          throw new Error(`Ledger file is corrupted at line ${index + 1}: not valid JSON.`);
        }
      });
  }

  get(id: string): LedgerEntry | undefined {
    return this.readAll().find((entry) => entry.id === id);
  }
}

export interface ChainVerificationResult {
  valid: boolean;
  entryCount: number;
  firstInvalidIndex: number | null;
  firstInvalidReason: string | null;
}

/**
 * Verifies both each entry's own signature/hash AND that the chain of prevHash
 * links is unbroken. An attacker who deletes or reorders a historical entry
 * (without also re-signing everything after it, which requires the private key)
 * is caught here, not just at the single-receipt level.
 */
export function verifyChain(entries: LedgerEntry[]): ChainVerificationResult {
  let expectedPrevHash: string | null = null;
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    const result = verifyReceipt(entry);
    if (!result.valid) {
      return { valid: false, entryCount: entries.length, firstInvalidIndex: i, firstInvalidReason: result.reason ?? "unknown" };
    }
    if (entry.prevHash !== expectedPrevHash) {
      return { valid: false, entryCount: entries.length, firstInvalidIndex: i, firstInvalidReason: "chain_broken" };
    }
    expectedPrevHash = entry.hash;
  }
  return { valid: true, entryCount: entries.length, firstInvalidIndex: null, firstInvalidReason: null };
}
