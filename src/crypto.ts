import {
  generateKeyPairSync,
  sign as nodeSign,
  verify as nodeVerify,
  createPrivateKey,
  createPublicKey,
  createHash
} from "node:crypto";
import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync } from "node:fs";
import { dirname } from "node:path";

export interface KeyPairPaths {
  privateKeyPath: string;
  publicKeyPath: string;
}

export interface LoadedKeyPair {
  privateKeyPem: string;
  publicKeyRawBase64: string;
}

/**
 * Ed25519 only. Node's built-in `crypto` module supports it natively (no external
 * crypto dependency) — smaller dependency surface for a signing tool is a deliberate
 * security choice, not an oversight.
 */
export function generateKeyPair(paths: KeyPairPaths): LoadedKeyPair {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const privateKeyPem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
  const publicKeyRaw = publicKey.export({ type: "spki", format: "der" });
  // Raw 32-byte Ed25519 public key is the last 32 bytes of the SPKI DER encoding.
  const publicKeyRawBase64 = publicKeyRaw.subarray(publicKeyRaw.length - 32).toString("base64");

  mkdirSync(dirname(paths.privateKeyPath), { recursive: true, mode: 0o700 });
  writeFileSync(paths.privateKeyPath, privateKeyPem, { mode: 0o600 });
  chmodSync(paths.privateKeyPath, 0o600);
  writeFileSync(paths.publicKeyPath, publicKeyRawBase64, { mode: 0o644 });

  return { privateKeyPem, publicKeyRawBase64 };
}

export function loadKeyPair(paths: KeyPairPaths): LoadedKeyPair {
  if (!existsSync(paths.privateKeyPath) || !existsSync(paths.publicKeyPath)) {
    throw new Error(
      `No signing key found at ${paths.privateKeyPath}. Run "computeledger keys generate" first.`
    );
  }
  const privateKeyPem = readFileSync(paths.privateKeyPath, "utf8");
  const publicKeyRawBase64 = readFileSync(paths.publicKeyPath, "utf8").trim();
  return { privateKeyPem, publicKeyRawBase64 };
}

export function signBytes(privateKeyPem: string, data: Uint8Array): string {
  const keyObject = createPrivateKey({ key: privateKeyPem, format: "pem" });
  const signature = nodeSign(null, Buffer.from(data), keyObject);
  return signature.toString("base64");
}

export function verifySignature(
  publicKeyRawBase64: string,
  data: Uint8Array,
  signatureBase64: string
): boolean {
  try {
    const rawKey = Buffer.from(publicKeyRawBase64, "base64");
    if (rawKey.length !== 32) return false;
    const spkiPrefix = Buffer.from("302a300506032b6570032100", "hex");
    const spkiDer = Buffer.concat([spkiPrefix, rawKey]);
    const keyObject = createPublicKey({ key: spkiDer, format: "der", type: "spki" });
    return nodeVerify(null, Buffer.from(data), keyObject, Buffer.from(signatureBase64, "base64"));
  } catch {
    return false;
  }
}

export function sha256Hex(data: Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}
