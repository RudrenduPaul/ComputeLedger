import { describe, expect, it } from "vitest";
import { isGpuAvailable, sampleGpuOnce } from "./gpu.js";

/**
 * These run against whatever `nvidia-smi` actually resolves to on the test
 * machine (usually absent in CI/dev). The point of the test is that neither
 * function throws or hangs when it's missing — a common case, not an error.
 */
describe("gpu sampling (best-effort, no NVIDIA GPU assumed)", () => {
  it("isGpuAvailable resolves to a boolean without throwing", async () => {
    const available = await isGpuAvailable();
    expect(typeof available).toBe("boolean");
  });

  it("sampleGpuOnce resolves to an array without throwing", async () => {
    const samples = await sampleGpuOnce();
    expect(Array.isArray(samples)).toBe(true);
  });
});
