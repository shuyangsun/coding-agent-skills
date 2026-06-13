// Run only the warm RAG sidecar (no web server):
//   bun run dev:rag
// Useful when running `bun run dev:web` separately, or alongside `bun run preview`.
import { SERVICE_URL, pipePrefixed, spawnSidecar } from "./_rag.mjs";

const rag = spawnSidecar();
pipePrefixed(rag, "rag", "36");
console.log(`[rag] warm RAG sidecar -> ${SERVICE_URL}`);

function shutdown() {
  try {
    rag.kill("SIGTERM");
  } catch {
    // already gone
  }
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
rag.on("exit", (code) => process.exit(code ?? 0));
