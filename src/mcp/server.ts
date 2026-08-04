import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { resolvePaths } from "../config.js";
import { loadKeyPair } from "../crypto.js";
import { createReceipt, verifyReceipt, type SignedReceipt } from "../receipt.js";
import { Ledger, verifyChain } from "../ledger.js";
import {
  RECORD_USAGE_TOOL_NAME,
  VERIFY_RECEIPT_TOOL_NAME,
  LIST_LEDGER_TOOL_NAME,
  VERIFY_LEDGER_TOOL_NAME,
  recordUsageInputShape,
  verifyReceiptInputShape,
  listLedgerInputShape,
  verifyLedgerInputShape
} from "./tool-schema.js";

function readPackageVersion(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  const pkgJsonPath = resolve(here, "..", "..", "package.json");
  const raw = readFileSync(pkgJsonPath, "utf8");
  return (JSON.parse(raw) as { version: string }).version;
}

export const PACKAGE_VERSION = readPackageVersion();

function jsonResult(data: unknown, isError = false): CallToolResult {
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }], isError };
}

export function createComputeLedgerMcpServer(): McpServer {
  const server = new McpServer({ name: "computeledger-cli", version: PACKAGE_VERSION });

  server.registerTool(
    RECORD_USAGE_TOOL_NAME,
    {
      title: "Record compute usage",
      description:
        "Records a compute usage entry, signs it with the local Ed25519 key, appends it to the hash-chained local ledger, and returns the signed receipt.",
      inputSchema: recordUsageInputShape
    },
    async (input): Promise<CallToolResult> => {
      try {
        const paths = resolvePaths({ local: input.local });
        const keyPair = loadKeyPair(paths);
        const ledger = new Ledger(paths.ledgerPath);
        const receipt = createReceipt(
          {
            provider: input.provider,
            hardware: input.hardware,
            durationSeconds: input.durationSeconds,
            gpuHours: input.gpuHours,
            estimatedFlops: input.estimatedFlops,
            workloadType: input.workloadType
          },
          ledger.getLastHash(),
          keyPair
        );
        ledger.append(receipt);
        return jsonResult(receipt);
      } catch (err) {
        return jsonResult({ error: err instanceof Error ? err.message : String(err) }, true);
      }
    }
  );

  server.registerTool(
    VERIFY_RECEIPT_TOOL_NAME,
    {
      title: "Verify a compute usage receipt",
      description: "Independently verifies a signed ComputeLedger receipt's cryptographic signature and hash integrity, without needing to trust the issuer.",
      inputSchema: verifyReceiptInputShape
    },
    async (input): Promise<CallToolResult> => {
      const result = verifyReceipt(input.receipt as unknown as SignedReceipt);
      return jsonResult(result, !result.valid);
    }
  );

  server.registerTool(
    LIST_LEDGER_TOOL_NAME,
    {
      title: "List ledger entries",
      description: "Lists every usage receipt recorded in the local ComputeLedger ledger.",
      inputSchema: listLedgerInputShape
    },
    async (input): Promise<CallToolResult> => {
      const paths = resolvePaths({ local: input.local });
      const entries = new Ledger(paths.ledgerPath).readAll();
      return jsonResult(entries);
    }
  );

  server.registerTool(
    VERIFY_LEDGER_TOOL_NAME,
    {
      title: "Verify the full ledger chain",
      description: "Verifies every entry's signature plus the unbroken hash chain across the entire local ledger, detecting tampering, deletion, or reordering.",
      inputSchema: verifyLedgerInputShape
    },
    async (input): Promise<CallToolResult> => {
      const paths = resolvePaths({ local: input.local });
      const entries = new Ledger(paths.ledgerPath).readAll();
      const result = verifyChain(entries);
      return jsonResult(result, !result.valid);
    }
  );

  return server;
}

export async function startServer(): Promise<void> {
  const server = createComputeLedgerMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
