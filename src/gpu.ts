import { spawn } from "node:child_process";

export interface GpuSample {
  utilizationPercent: number;
  memoryUsedMib: number;
}

/**
 * Best-effort GPU utilization sampling via nvidia-smi. Never throws: a machine
 * with no NVIDIA GPU (most CI runners, most laptops) is the common case, not an
 * error case, so absence of nvidia-smi degrades to an empty sample list rather
 * than failing the whole `run` command.
 */
export async function sampleGpuOnce(): Promise<GpuSample[]> {
  return new Promise((resolve) => {
    const proc = spawn("nvidia-smi", [
      "--query-gpu=utilization.gpu,memory.used",
      "--format=csv,noheader,nounits"
    ]);
    let stdout = "";
    proc.stdout?.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    proc.on("error", () => resolve([]));
    proc.on("close", (code) => {
      if (code !== 0 || !stdout.trim()) {
        resolve([]);
        return;
      }
      const samples = stdout
        .trim()
        .split("\n")
        .map((line) => {
          const [util, mem] = line.split(",").map((s) => Number.parseFloat(s.trim()));
          return { utilizationPercent: util, memoryUsedMib: mem };
        })
        .filter((s) => Number.isFinite(s.utilizationPercent) && Number.isFinite(s.memoryUsedMib));
      resolve(samples);
    });
  });
}

export function isGpuAvailable(): Promise<boolean> {
  return new Promise((resolve) => {
    const proc = spawn("nvidia-smi", ["-L"]);
    proc.on("error", () => resolve(false));
    proc.on("close", (code) => resolve(code === 0));
  });
}
