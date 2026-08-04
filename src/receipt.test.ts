import { describe, expect, it, beforeEach } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { generateKeyPair } from "./crypto.js";
import { createReceipt, verifyReceipt, hashPayload } from "./receipt.js";

describe("receipt", () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "computeledger-test-"));
  });

  function keyPair() {
    return generateKeyPair({
      privateKeyPath: join(dir, "keys", "ed25519.pem"),
      publicKeyPath: join(dir, "keys", "ed25519.pub")
    });
  }

  it("creates a receipt that verifies successfully", () => {
    const kp = keyPair();
    const receipt = createReceipt(
      { provider: "aws", hardware: "nvidia-h100", durationSeconds: 120, workloadType: "training" },
      null,
      kp
    );
    expect(verifyReceipt(receipt)).toEqual({ valid: true });
  });

  it("rejects a receipt whose payload was tampered with after signing", () => {
    const kp = keyPair();
    const receipt = createReceipt(
      { provider: "aws", hardware: "nvidia-h100", durationSeconds: 120 },
      null,
      kp
    );
    const tampered = { ...receipt, usage: { ...receipt.usage, durationSeconds: 999999 } };
    const result = verifyReceipt(tampered);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("hash_mismatch");
  });

  it("rejects a receipt with a forged signature under a substituted public key", () => {
    const kp = keyPair();
    const attackerKp = generateKeyPair({
      privateKeyPath: join(dir, "attacker-keys", "ed25519.pem"),
      publicKeyPath: join(dir, "attacker-keys", "ed25519.pub")
    });
    const receipt = createReceipt(
      { provider: "aws", hardware: "nvidia-h100", durationSeconds: 120 },
      null,
      kp
    );
    // Attacker swaps in their own public key but keeps the original signature —
    // the hash changes because publicKey is part of the signed payload, so this
    // must fail even before signature verification runs.
    const forged = { ...receipt, publicKey: attackerKp.publicKeyRawBase64 };
    const result = verifyReceipt(forged);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("hash_mismatch");
  });

  it("rejects an unsupported receipt version", () => {
    const kp = keyPair();
    const receipt = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 1 }, null, kp);
    const result = verifyReceipt({ ...receipt, version: "999" });
    expect(result).toEqual({ valid: false, reason: "unsupported_version" });
  });

  it("chains prevHash across successive receipts", () => {
    const kp = keyPair();
    const first = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 1 }, null, kp);
    const second = createReceipt({ provider: "aws", hardware: "cpu", durationSeconds: 2 }, first.hash, kp);
    expect(second.prevHash).toBe(first.hash);
    expect(hashPayload(first)).not.toBe(hashPayload(second));
  });
});
