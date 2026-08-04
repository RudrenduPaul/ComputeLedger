export function printResult(data: unknown, humanText: string, json: boolean): void {
  if (json) {
    process.stdout.write(`${JSON.stringify(data, null, 2)}\n`);
  } else {
    process.stdout.write(`${humanText}\n`);
  }
}

export function printError(message: string, json: boolean): void {
  if (json) {
    process.stderr.write(`${JSON.stringify({ error: message }, null, 2)}\n`);
  } else {
    process.stderr.write(`Error: ${message}\n`);
  }
}
