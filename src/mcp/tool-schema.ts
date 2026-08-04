import { z } from "zod";

export const RECORD_USAGE_TOOL_NAME = "record_usage";
export const VERIFY_RECEIPT_TOOL_NAME = "verify_receipt";
export const LIST_LEDGER_TOOL_NAME = "list_ledger";
export const VERIFY_LEDGER_TOOL_NAME = "verify_ledger";

export const recordUsageInputShape = {
  provider: z.string().describe("Compute provider name, e.g. 'aws', 'lambda-labs', 'on-prem'"),
  hardware: z.string().describe("Hardware identifier, e.g. 'nvidia-h100', 'nvidia-a100', 'cpu'"),
  durationSeconds: z.number().nonnegative().describe("Wall-clock duration of the workload in seconds"),
  gpuHours: z.number().nonnegative().optional().describe("GPU-hours consumed, if known"),
  estimatedFlops: z.number().nonnegative().optional().describe("Estimated floating point operations, if known"),
  workloadType: z.enum(["training", "inference", "unknown"]).optional(),
  local: z.boolean().optional().describe("Use the current directory's .computeledger instead of the home directory")
};

export const verifyReceiptInputShape = {
  receipt: z.record(z.string(), z.unknown()).describe("A signed ComputeLedger receipt object, as produced by record_usage or `computeledger record`")
};

export const listLedgerInputShape = {
  local: z.boolean().optional()
};

export const verifyLedgerInputShape = {
  local: z.boolean().optional()
};
