import { describe, expect, it } from "vitest";
import { resolvePaths } from "./config.js";

describe("resolvePaths", () => {
  it("defaults to the home directory", () => {
    const paths = resolvePaths({ home: "/home/user", cwd: "/repo" });
    expect(paths.privateKeyPath).toBe("/home/user/.computeledger/keys/ed25519.pem");
    expect(paths.ledgerPath).toBe("/home/user/.computeledger/ledger.jsonl");
  });

  it("uses the current directory when local is true", () => {
    const paths = resolvePaths({ local: true, home: "/home/user", cwd: "/repo" });
    expect(paths.privateKeyPath).toBe("/repo/.computeledger/keys/ed25519.pem");
    expect(paths.ledgerPath).toBe("/repo/.computeledger/ledger.jsonl");
  });
});
