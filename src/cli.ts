#!/usr/bin/env node
import { readFileSync, existsSync } from "node:fs";
import { resolvePaths } from "./config.js";
import { generateKeyPair, loadKeyPair } from "./crypto.js";
import { createReceipt, verifyReceipt, type SignedReceipt, type WorkloadType } from "./receipt.js";
import { Ledger, verifyChain } from "./ledger.js";
import { runAndMeasure } from "./run.js";
import { printResult, printError } from "./output.js";

const VERSION = "0.1.0";

function hasFlag(args: string[], name: string): boolean {
  return args.includes(name);
}

function getOption(args: string[], name: string): string | undefined {
  const idx = args.indexOf(name);
  if (idx === -1 || idx === args.length - 1) return undefined;
  return args[idx + 1];
}

function splitOnDoubleDash(args: string[]): { flags: string[]; command: string[] } {
  const dashIdx = args.indexOf("--");
  if (dashIdx === -1) return { flags: args, command: [] };
  return { flags: args.slice(0, dashIdx), command: args.slice(dashIdx + 1) };
}

function parseWorkloadType(raw: string | undefined): WorkloadType {
  if (raw === "training" || raw === "inference" || raw === "unknown") return raw;
  return "unknown";
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const [command, ...rest] = argv;
  const json = hasFlag(rest, "--json") || hasFlag(argv, "--json");

  try {
    switch (command) {
      case undefined:
      case "--help":
      case "-h":
        printHelp();
        return;
      case "--version":
      case "-v":
        process.stdout.write(`${VERSION}\n`);
        return;
      case "keys":
        await handleKeys(rest, json);
        return;
      case "run":
        await handleRun(rest, json);
        return;
      case "record":
        await handleRecord(rest, json);
        return;
      case "verify":
        await handleVerify(rest, json);
        return;
      case "ledger":
        await handleLedger(rest, json);
        return;
      case "export":
        await handleExport(rest, json);
        return;
      case "mcp":
        await import("./mcp/server.js").then((m) => m.startServer());
        return;
      default:
        printError(`Unknown command "${command}". Run "computeledger --help".`, json);
        process.exitCode = 1;
    }
  } catch (err) {
    printError(err instanceof Error ? err.message : String(err), json);
    process.exitCode = 1;
  }
}

function printHelp(): void {
  process.stdout.write(`computeledger v${VERSION}

Provider-agnostic CLI for signing, hash-chaining, and verifying compute usage receipts.

Usage:
  computeledger keys generate [--local]
  computeledger keys show [--local] [--json]
  computeledger run [--local] [--provider <name>] [--hardware <type>] [--workload-type training|inference|unknown] [--no-record-command] [--json] -- <command...>
  computeledger record --provider <name> --hardware <type> --duration-seconds <n> [--gpu-hours <n>] [--flops <n>] [--workload-type <type>] [--local] [--json]
  computeledger verify <receipt.json> [--json]
  computeledger ledger list [--local] [--json]
  computeledger ledger show <id> [--local] [--json]
  computeledger ledger verify [--local] [--json]
  computeledger export --format json|csv [--out <file>] [--local]
  computeledger mcp

Flags:
  --local   Use ./.computeledger in the current directory instead of ~/.computeledger
  --json    Structured JSON output on stdout, suitable for agent/programmatic use
`);
}

async function handleKeys(rest: string[], json: boolean): Promise<void> {
  const [sub, ...flags] = rest;
  const local = hasFlag(flags, "--local");
  const paths = resolvePaths({ local });

  if (sub === "generate") {
    const keyPair = generateKeyPair(paths);
    printResult(
      { publicKey: keyPair.publicKeyRawBase64, privateKeyPath: paths.privateKeyPath, publicKeyPath: paths.publicKeyPath },
      `Generated Ed25519 keypair.\nPublic key: ${keyPair.publicKeyRawBase64}\nPrivate key: ${paths.privateKeyPath} (mode 600)`,
      json
    );
    return;
  }
  if (sub === "show") {
    const keyPair = loadKeyPair(paths);
    printResult({ publicKey: keyPair.publicKeyRawBase64 }, keyPair.publicKeyRawBase64, json);
    return;
  }
  printError(`Unknown "keys" subcommand "${sub}". Use "generate" or "show".`, json);
  process.exitCode = 1;
}

async function handleRun(rest: string[], json: boolean): Promise<void> {
  const { flags, command } = splitOnDoubleDash(rest);
  if (command.length === 0) {
    printError('Usage: computeledger run [flags] -- <command> [args...]', json);
    process.exitCode = 1;
    return;
  }
  const local = hasFlag(flags, "--local");
  const provider = getOption(flags, "--provider") ?? "unknown";
  const hardware = getOption(flags, "--hardware") ?? "unknown";
  const workloadType = parseWorkloadType(getOption(flags, "--workload-type"));
  const recordCommand = !hasFlag(flags, "--no-record-command");

  const paths = resolvePaths({ local });
  const keyPair = loadKeyPair(paths);
  const ledger = new Ledger(paths.ledgerPath);

  const result = await runAndMeasure(command);

  const receipt = createReceipt(
    {
      provider,
      hardware,
      durationSeconds: result.durationSeconds,
      gpuHours: result.gpuUtilizationSamples.length > 0 ? (result.durationSeconds / 3600) : undefined,
      gpuUtilizationSamples: result.gpuUtilizationSamples.length > 0 ? result.gpuUtilizationSamples : undefined,
      workloadType,
      command: recordCommand ? command.join(" ") : undefined
    },
    ledger.getLastHash(),
    keyPair
  );
  ledger.append(receipt);

  printResult(
    receipt,
    `Job exited ${result.exitCode}. Recorded usage receipt ${receipt.id} (${result.durationSeconds.toFixed(2)}s, ${result.gpuUtilizationSamples.length} GPU samples).`,
    json
  );
  process.exitCode = result.exitCode;
}

async function handleRecord(rest: string[], json: boolean): Promise<void> {
  const local = hasFlag(rest, "--local");
  const provider = getOption(rest, "--provider");
  const hardware = getOption(rest, "--hardware");
  const durationRaw = getOption(rest, "--duration-seconds");
  const gpuHoursRaw = getOption(rest, "--gpu-hours");
  const flopsRaw = getOption(rest, "--flops");
  const workloadType = parseWorkloadType(getOption(rest, "--workload-type"));

  if (!provider || !hardware || durationRaw === undefined) {
    printError("Usage: computeledger record --provider <name> --hardware <type> --duration-seconds <n> [--gpu-hours <n>] [--flops <n>] [--workload-type <type>]", json);
    process.exitCode = 1;
    return;
  }
  const durationSeconds = Number.parseFloat(durationRaw);
  if (!Number.isFinite(durationSeconds) || durationSeconds < 0) {
    printError("--duration-seconds must be a non-negative number", json);
    process.exitCode = 1;
    return;
  }
  let gpuHours: number | undefined;
  if (gpuHoursRaw !== undefined) {
    gpuHours = Number.parseFloat(gpuHoursRaw);
    if (!Number.isFinite(gpuHours) || gpuHours < 0) {
      printError("--gpu-hours must be a non-negative number", json);
      process.exitCode = 1;
      return;
    }
  }
  let estimatedFlops: number | undefined;
  if (flopsRaw !== undefined) {
    estimatedFlops = Number.parseFloat(flopsRaw);
    if (!Number.isFinite(estimatedFlops) || estimatedFlops < 0) {
      printError("--flops must be a non-negative number", json);
      process.exitCode = 1;
      return;
    }
  }

  const paths = resolvePaths({ local });
  const keyPair = loadKeyPair(paths);
  const ledger = new Ledger(paths.ledgerPath);

  const receipt = createReceipt(
    {
      provider,
      hardware,
      durationSeconds,
      gpuHours,
      estimatedFlops,
      workloadType
    },
    ledger.getLastHash(),
    keyPair
  );
  ledger.append(receipt);

  printResult(receipt, `Recorded usage receipt ${receipt.id}.`, json);
}

async function handleVerify(rest: string[], json: boolean): Promise<void> {
  const filePath = rest.find((a) => !a.startsWith("--"));
  if (!filePath) {
    printError("Usage: computeledger verify <receipt.json>", json);
    process.exitCode = 1;
    return;
  }
  if (!existsSync(filePath)) {
    printError(`File not found: ${filePath}`, json);
    process.exitCode = 1;
    return;
  }
  let receipt: SignedReceipt;
  try {
    receipt = JSON.parse(readFileSync(filePath, "utf8"));
  } catch {
    printError(`File is not valid JSON: ${filePath}`, json);
    process.exitCode = 1;
    return;
  }
  const result = verifyReceipt(receipt);
  printResult(
    result,
    result.valid ? "Receipt is valid: signature and hash match." : `Receipt is INVALID: ${result.reason}`,
    json
  );
  process.exitCode = result.valid ? 0 : 1;
}

async function handleLedger(rest: string[], json: boolean): Promise<void> {
  const [sub, ...flags] = rest;
  const local = hasFlag(flags, "--local") || hasFlag(rest, "--local");
  const paths = resolvePaths({ local });
  const ledger = new Ledger(paths.ledgerPath);

  if (sub === "list") {
    const entries = ledger.readAll();
    printResult(
      entries,
      entries.map((e) => `${e.id}  ${e.timestamp}  ${e.provider}/${e.hardware}  ${e.usage.durationSeconds.toFixed(1)}s`).join("\n") || "(empty ledger)",
      json
    );
    return;
  }
  if (sub === "show") {
    const id = flags.find((a) => !a.startsWith("--"));
    if (!id) {
      printError("Usage: computeledger ledger show <id>", json);
      process.exitCode = 1;
      return;
    }
    const entry = ledger.get(id);
    if (!entry) {
      printError(`No ledger entry with id ${id}`, json);
      process.exitCode = 1;
      return;
    }
    printResult(entry, JSON.stringify(entry, null, 2), json);
    return;
  }
  if (sub === "verify") {
    const result = verifyChain(ledger.readAll());
    printResult(
      result,
      result.valid
        ? `Ledger valid: ${result.entryCount} entries, unbroken hash chain.`
        : `Ledger INVALID at entry ${result.firstInvalidIndex}: ${result.firstInvalidReason}`,
      json
    );
    process.exitCode = result.valid ? 0 : 1;
    return;
  }
  printError(`Unknown "ledger" subcommand "${sub}". Use "list", "show", or "verify".`, json);
  process.exitCode = 1;
}

async function handleExport(rest: string[], json: boolean): Promise<void> {
  const local = hasFlag(rest, "--local");
  const format = getOption(rest, "--format") ?? "json";
  const outPath = getOption(rest, "--out");
  const paths = resolvePaths({ local });
  const entries = new Ledger(paths.ledgerPath).readAll();

  let output: string;
  if (format === "csv") {
    const header = "id,timestamp,provider,hardware,durationSeconds,gpuHours,workloadType";
    const rows = entries.map(
      (e) =>
        `${e.id},${e.timestamp},${e.provider},${e.hardware},${e.usage.durationSeconds},${e.usage.gpuHours ?? ""},${e.usage.workloadType}`
    );
    output = [header, ...rows].join("\n");
  } else {
    output = JSON.stringify(entries, null, 2);
  }

  if (outPath) {
    const { writeFileSync } = await import("node:fs");
    writeFileSync(outPath, output);
    printResult({ written: outPath, count: entries.length }, `Exported ${entries.length} entries to ${outPath}`, json);
  } else {
    process.stdout.write(`${output}\n`);
  }
}

main();
