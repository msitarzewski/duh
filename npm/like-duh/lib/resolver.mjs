import { execFileSync } from "node:child_process";
import { DUH_MIN_VERSION } from "./constants.mjs";

/**
 * Try spawning a command and return true if it produces valid duh output.
 * Guards against the wrong "duh" package (PyPI name squatter).
 */
function canRun(command, args) {
  try {
    const output = execFileSync(command, args, {
      stdio: "pipe",
      timeout: 15_000,
      encoding: "utf-8",
    });
    return output.includes("duh, version");
  } catch {
    return false;
  }
}

/**
 * Parse a semver-ish version string like "duh 0.6.0" or "0.6.0" into [major, minor, patch].
 */
function parseVersion(output) {
  const match = output.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/**
 * Compare two [major, minor, patch] tuples. Returns -1, 0, or 1.
 */
function compareVersions(a, b) {
  for (let i = 0; i < 3; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return 0;
}

/**
 * Check the version of duh at the given command + prefix.
 * Warns if below minimum, but never blocks.
 */
function checkVersion(command, prefix) {
  try {
    const output = execFileSync(command, [...prefix, "--version"], {
      stdio: "pipe",
      timeout: 15_000,
      encoding: "utf-8",
    });
    const version = parseVersion(output);
    const minVersion = parseVersion(DUH_MIN_VERSION);
    if (version && minVersion && compareVersions(version, minVersion) < 0) {
      const vStr = version.join(".");
      console.error(
        `Warning: duh ${vStr} found, but ${DUH_MIN_VERSION}+ recommended. ` +
          `Run: pip install --upgrade duh`
      );
    }
  } catch {
    // Version check is best-effort; don't block.
  }
}

/**
 * Resolve the duh executable. Returns { command, prefix } or null.
 *
 * Resolution order:
 * 1. DUH_PATH env var
 * 2. duh on PATH
 * 3. uvx duh
 * 4. pipx run duh
 */
export function resolve() {
  // 1. Explicit override
  const duhPath = process.env.DUH_PATH;
  if (duhPath) {
    if (canRun(duhPath, ["--version"])) {
      checkVersion(duhPath, []);
      return { command: duhPath, prefix: [] };
    }
    console.error(`Warning: DUH_PATH="${duhPath}" is set but not executable.`);
  }

  // 2. duh on PATH
  if (canRun("duh", ["--version"])) {
    checkVersion("duh", []);
    return { command: "duh", prefix: [] };
  }

  // 3. uvx duh
  if (canRun("uvx", ["duh", "--version"])) {
    checkVersion("uvx", ["duh"]);
    return { command: "uvx", prefix: ["duh"] };
  }

  // 4. pipx run duh
  if (canRun("pipx", ["run", "duh", "--version"])) {
    checkVersion("pipx", ["run", "duh"]);
    return { command: "pipx", prefix: ["run", "duh"] };
  }

  return null;
}
