// Shared helpers for launching the warm RAG sidecar (rag-service/serve.py).
// Used by scripts/dev.mjs (sidecar + Vite) and scripts/rag-service.mjs (sidecar only).
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const inceptionRoot = path.resolve(here, ".."); // <repo>/inception
export const repoRoot = path.resolve(here, "../.."); // <repo>

export const SERVICE_HOST = process.env.RAG_SERVICE_HOST ?? "127.0.0.1";
export const SERVICE_PORT = process.env.RAG_SERVICE_PORT ?? "8390";
export const SERVICE_URL = `http://${SERVICE_HOST}:${SERVICE_PORT}`;

/** The rag-skill venv Python (has qdrant-client + fastembed), or python3. */
export function resolvePython() {
  if (process.env.RAG_PYTHON) return process.env.RAG_PYTHON;
  const venv = path.join(homedir(), ".cache/rag-skill/venv/bin/python");
  return existsSync(venv) ? venv : "python3";
}

/** The setting-up-rag skill scripts dir that exports rag_lib + answer. */
export function resolveScriptsDir() {
  return (
    process.env.RAG_SCRIPTS_DIR ??
    path.join(repoRoot, ".agents/skills/setting-up-rag/scripts")
  );
}

export function spawnSidecar() {
  const python = resolvePython();
  const serve = path.join(inceptionRoot, "rag-service/serve.py");
  return spawn(python, [serve], {
    cwd: inceptionRoot,
    env: {
      ...process.env,
      RAG_SERVICE_HOST: SERVICE_HOST,
      RAG_SERVICE_PORT: SERVICE_PORT,
      RAG_SCRIPTS_DIR: resolveScriptsDir(),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
}

/** Tag each child output line with a colored [label] so two processes read clearly. */
export function pipePrefixed(child, label, color) {
  const tag = `\x1b[${color}m[${label}]\x1b[0m `;
  const forward = (out) => (buf) => {
    for (const line of buf.toString().split("\n")) {
      if (line.length) out.write(`${tag}${line}\n`);
    }
  };
  child.stdout?.on("data", forward(process.stdout));
  child.stderr?.on("data", forward(process.stderr));
}
