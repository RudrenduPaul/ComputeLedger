import { randomUUID } from "node:crypto";
import { canonicalizeToBytes } from "./canonical.js";
import { signBytes, verifySignature, sha256Hex, type LoadedKeyPair } from "./crypto.js";

export const RECEIPT_VERSION = "1";

export type WorkloadType = "training" | "inference" | "unknown";

export interface UsageInput {
  provider: string;
  hardware: string;
  durationSeconds: number;
  gpuHours?: number;
  estimatedFlops?: number;
  gpuUtilizationSamples?: number[];
  workloadType?: WorkloadType;
  command?: string;
}

export interface ReceiptPayload {
  version: string;
  id: string;
  timestamp: string;
  provider: string;
  hardware: string;
  usage: {
    durationSeconds: number;
    gpuHours: number | null;
    estimatedFlops: number | null;
    gpuUtilizationSamples: number[] | null;
    workloadType: WorkloadType;
  };
  command: string | null;
  prevHash: string | null;
  publicKey: string;
}

export interface SignedReceipt extends ReceiptPayload {
  hash: string;
  signature: string;
}

function buildPayload(input: UsageInput, prevHash: string | null, publicKey: string): ReceiptPayload {
  if (input.durationSeconds < 0) {
    throw new Error("durationSeconds must be >= 0");
  }
  return {
    version: RECEIPT_VERSION,
    id: randomUUID(),
    timestamp: new Date().toISOString(),
    provider: input.provider,
    hardware: input.hardware,
    usage: {
      durationSeconds: input.durationSeconds,
      gpuHours: input.gpuHours ?? null,
      estimatedFlops: input.estimatedFlops ?? null,
      gpuUtilizationSamples: input.gpuUtilizationSamples ?? null,
      workloadType: input.workloadType ?? "unknown"
    },
    command: input.command ?? null,
    prevHash,
    publicKey
  };
}

/**
 * The hash covers every field an attacker could tamper with, including publicKey
 * and prevHash — binding the signer's identity and chain position into the signed
 * digest is what stops a receipt being replayed under a different key or spliced
 * into a different position in the chain.
 */
export function hashPayload(payload: ReceiptPayload): string {
  return sha256Hex(canonicalizeToBytes(payload));
}

export function createReceipt(
  input: UsageInput,
  prevHash: string | null,
  keyPair: LoadedKeyPair
): SignedReceipt {
  const payload = buildPayload(input, prevHash, keyPair.publicKeyRawBase64);
  const hash = hashPayload(payload);
  const signature = signBytes(keyPair.privateKeyPem, Buffer.from(hash, "hex"));
  return { ...payload, hash, signature };
}

export type VerifyFailureReason =
  | "invalid_signature"
  | "hash_mismatch"
  | "unsupported_version"
  | "malformed_receipt";

export interface VerifyResult {
  valid: boolean;
  reason?: VerifyFailureReason;
}

export function verifyReceipt(receipt: SignedReceipt): VerifyResult {
  if (!receipt || typeof receipt !== "object") {
    return { valid: false, reason: "malformed_receipt" };
  }
  if (receipt.version !== RECEIPT_VERSION) {
    return { valid: false, reason: "unsupported_version" };
  }
  const { hash, signature, ...payload } = receipt;
  let recomputedHash: string;
  try {
    recomputedHash = hashPayload(payload as ReceiptPayload);
  } catch {
    return { valid: false, reason: "malformed_receipt" };
  }
  if (recomputedHash !== hash) {
    return { valid: false, reason: "hash_mismatch" };
  }
  const sigValid = verifySignature(payload.publicKey, Buffer.from(hash, "hex"), signature);
  if (!sigValid) {
    return { valid: false, reason: "invalid_signature" };
  }
  return { valid: true };
}
