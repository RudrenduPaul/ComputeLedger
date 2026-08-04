import { spawn } from "node:child_process";
import { sampleGpuOnce } from "./gpu.js";

export interface RunResult {
  exitCode: number;
  durationSeconds: number;
  gpuUtilizationSamples: number[];
}

/**
 * Executes the wrapped command via argv array (never a shell string), so shell
 * metacharacters in a user-supplied command are inert rather than re-interpreted.
 * This is the load-bearing security property of `computeledger run -- <command>`.
 */
export function runAndMeasure(command: string[], sampleIntervalMs = 2000): Promise<RunResult> {
  if (command.length === 0) {
    throw new Error("No command given. Usage: computeledger run -- <command> [args...]");
  }
  return new Promise((resolve, reject) => {
    const start = process.hrtime.bigint();
    const samples: number[] = [];
    const child = spawn(command[0], command.slice(1), { stdio: "inherit", shell: false });

    const sampler = setInterval(() => {
      sampleGpuOnce()
        .then((gpuSamples) => {
          for (const s of gpuSamples) samples.push(s.utilizationPercent);
        })
        .catch(() => undefined);
    }, sampleIntervalMs);

    child.on("error", (err) => {
      clearInterval(sampler);
      reject(err);
    });

    child.on("close", (code) => {
      clearInterval(sampler);
      const end = process.hrtime.bigint();
      const durationSeconds = Number(end - start) / 1e9;
      resolve({ exitCode: code ?? 1, durationSeconds, gpuUtilizationSamples: samples });
    });
  });
}
