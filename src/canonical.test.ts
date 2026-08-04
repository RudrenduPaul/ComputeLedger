import { describe, expect, it } from "vitest";
import { canonicalize } from "./canonical.js";

describe("canonicalize", () => {
  it("sorts object keys regardless of insertion order", () => {
    const a = canonicalize({ b: 1, a: 2 });
    const b = canonicalize({ a: 2, b: 1 });
    expect(a).toBe(b);
    expect(a).toBe('{"a":2,"b":1}');
  });

  it("sorts nested object keys recursively", () => {
    const out = canonicalize({ z: { d: 1, c: 2 }, a: 1 });
    expect(out).toBe('{"a":1,"z":{"c":2,"d":1}}');
  });

  it("preserves array order (arrays are not sorted)", () => {
    expect(canonicalize([3, 1, 2])).toBe("[3,1,2]");
  });

  it("drops keys with undefined values", () => {
    expect(canonicalize({ a: 1, b: undefined })).toBe('{"a":1}');
  });

  it("renders null explicitly", () => {
    expect(canonicalize({ a: null })).toBe('{"a":null}');
  });

  it("rejects non-finite numbers", () => {
    expect(() => canonicalize({ a: Number.NaN })).toThrow();
    expect(() => canonicalize({ a: Number.POSITIVE_INFINITY })).toThrow();
  });

  it("produces identical output for structurally identical but differently ordered deep objects", () => {
    const p1 = { usage: { durationSeconds: 10, workloadType: "training" }, provider: "aws" };
    const p2 = { provider: "aws", usage: { workloadType: "training", durationSeconds: 10 } };
    expect(canonicalize(p1)).toBe(canonicalize(p2));
  });
});
