import { createRequire } from "node:module";

/**
 * Single source of truth for the package version at runtime. Reads it straight
 * from the published package.json instead of a hardcoded string literal, so
 * `computeledger --version` can never drift from the actual npm package version
 * the way it previously did (the CLI kept reporting "0.1.0" while package.json
 * had already moved on to 0.1.1).
 *
 * createRequire (rather than a static `import ... from "../package.json"`) is
 * used deliberately: a static JSON import would need package.json to live
 * under tsconfig's `rootDir` ("src"), which it does not.
 */
const require = createRequire(import.meta.url);
const pkg = require("../package.json") as { version: string };

export const VERSION: string = pkg.version;
