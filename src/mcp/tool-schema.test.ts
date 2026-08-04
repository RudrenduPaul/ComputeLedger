import { describe, expect, it } from "vitest";
import { z } from "zod";
import { recordUsageInputShape, verifyReceiptInputShape } from "./tool-schema.js";

describe("MCP tool schemas", () => {
  it("recordUsageInputShape accepts a minimal valid payload", () => {
    const schema = z.object(recordUsageInputShape);
    const parsed = schema.parse({ provider: "aws", hardware: "nvidia-h100", durationSeconds: 30 });
    expect(parsed.provider).toBe("aws");
  });

  it("recordUsageInputShape rejects a negative duration", () => {
    const schema = z.object(recordUsageInputShape);
    expect(() => schema.parse({ provider: "aws", hardware: "cpu", durationSeconds: -1 })).toThrow();
  });

  it("recordUsageInputShape rejects an invalid workloadType enum value", () => {
    const schema = z.object(recordUsageInputShape);
    expect(() =>
      schema.parse({ provider: "aws", hardware: "cpu", durationSeconds: 1, workloadType: "not-a-real-type" })
    ).toThrow();
  });

  it("verifyReceiptInputShape requires a receipt object", () => {
    const schema = z.object(verifyReceiptInputShape);
    expect(() => schema.parse({})).toThrow();
    expect(schema.parse({ receipt: { id: "x" } }).receipt).toEqual({ id: "x" });
  });
});
