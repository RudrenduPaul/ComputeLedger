import { describe, expect, it, beforeEach } from "vitest";
import { mkdtempSync, appendFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { generateKeyPair } from "./crypto.js";
import { createReceipt } from "./receipt.js";
import { Ledger, verifyChain } from "./ledger.js";

describe("Ledger", () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "computeledger-ledger-test-"));
  });

  function keyPair() {
    return generateKeyPair({
      privateKeyPath: join(dir, "keys", "ed25519.pem"),
      publicKeyPath: join(dir, "keys", "ed25519.pub")
    });
  }

  it("appends entries and reads them back in order", () => {
    const kp = keyPair();
    const ledger = new Ledger(join(dir, "ledger.jsonl"));
    const r1 = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 1 }, ledger.getLastHash(), kp);
    ledger.append(r1);
    const r2 = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 2 }, ledger.getLastHash(), kp);
    ledger.append(r2);

    const all = ledger.readAll();
    expect(all.map((e) => e.id)).toEqual([r1.id, r2.id]);
  });

  it("verifies a valid unbroken chain", () => {
    const kp = keyPair();
    const ledger = new Ledger(join(dir, "ledger.jsonl"));
    for (let i = 0; i < 5; i++) {
      const receipt = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: i }, ledger.getLastHash(), kp);
      ledger.append(receipt);
    }
    const result = verifyChain(ledger.readAll());
    expect(result).toEqual({ valid: true, entryCount: 5, firstInvalidIndex: null, firstInvalidReason: null });
  });

  it("detects a deleted middle entry (chain_broken)", () => {
    const kp = keyPair();
    const ledger = new Ledger(join(dir, "ledger.jsonl"));
    const entries = [];
    for (let i = 0; i < 3; i++) {
      const receipt = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: i }, ledger.getLastHash(), kp);
      ledger.append(receipt);
      entries.push(receipt);
    }
    // Simulate deletion of the middle entry by verifying a spliced array directly.
    const spliced = [entries[0], entries[2]];
    const result = verifyChain(spliced);
    expect(result.valid).toBe(false);
    expect(result.firstInvalidReason).toBe("chain_broken");
    expect(result.firstInvalidIndex).toBe(1);
  });

  it("detects a tampered historical entry even if the chain links look intact", () => {
    const kp = keyPair();
    const receipt = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 10 }, null, kp);
    const tampered = { ...receipt, usage: { ...receipt.usage, durationSeconds: 10000 } };
    const result = verifyChain([tampered]);
    expect(result.valid).toBe(false);
    expect(result.firstInvalidReason).toBe("hash_mismatch");
  });

  it("raises a clear error instead of an uncaught crash on a corrupted ledger line", () => {
    const ledgerPath = join(dir, "ledger.jsonl");
    mkdirSync(dir, { recursive: true });
    appendFileSync(ledgerPath, "not valid json\n");
    const ledger = new Ledger(ledgerPath);
    expect(() => ledger.readAll()).toThrow(/corrupted at line 1/);
  });
});
