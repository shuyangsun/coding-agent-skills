// One command to run the whole GUI: the warm RAG sidecar + the Vite dev server.
//   bun run dev
// The sidecar keeps the embedding/reranker models hot so queries stay fast; Vite
// serves the TanStack Start app, which proxies to the sidecar at RAG_SERVICE_URL.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import {
  SERVICE_URL,
  inceptionRoot,
  pipePrefixed,
  spawnSidecar,
} from "./_rag.mjs";

const rag = spawnSidecar();
pipePrefixed(rag, "rag", "36"); // cyan

const viteBin = path.join(inceptionRoot, "node_modules/.bin/vite");
const web = spawn(
  existsSync(viteBin) ? viteBin : "vite",
  ["dev", "--port", process.env.PORT ?? "3000"],
  {
    cwd: inceptionRoot,
    env: { ...process.env, RAG_SERVICE_URL: SERVICE_URL },
    stdio: ["inherit", "pipe", "pipe"],
  },
);
pipePrefixed(web, "web", "35"); // magenta

let exiting = false;
function shutdown(code) {
  if (exiting) return;
  exiting = true;
  for (const child of [rag, web]) {
    try {
      child.kill("SIGTERM");
    } catch {
      // already gone
    }
  }
  setTimeout(() => process.exit(code ?? 0), 200);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
rag.on("exit", (code) => {
  console.error(`[rag] sidecar exited (${code}) — stopping dev server`);
  shutdown(code ?? 1);
});
web.on("exit", (code) => {
  console.error(`[web] dev server exited (${code}) — stopping sidecar`);
  shutdown(code ?? 0);
});
