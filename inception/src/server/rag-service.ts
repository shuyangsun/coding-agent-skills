// Thin server-only client for the warm RAG sidecar (rag-service/serve.py).
// Only ever imported from server-function handlers, so `process`/`fetch` here
// run on the server. The sidecar may still be starting up when the first
// request lands (the dev launcher spawns it alongside Vite), so connection
// failures are retried for a short window before surfacing.

export class RagServiceError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "RagServiceError";
    this.status = status;
  }
}

function serviceUrl(): string {
  return process.env.RAG_SERVICE_URL ?? "http://127.0.0.1:8390";
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type RagFetchInit = { method?: "GET" | "POST"; body?: unknown };

export async function ragFetch<T>(
  path: string,
  init: RagFetchInit = {},
): Promise<T> {
  const base = serviceUrl();
  const url = `${base}${path}`;
  const deadline = Date.now() + 20_000;
  let lastError: unknown;

  for (;;) {
    try {
      const response = await fetch(url, {
        method: init.method ?? "GET",
        headers: init.body ? { "Content-Type": "application/json" } : undefined,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
      });
      const raw = await response.text();
      const parsed: unknown = raw ? JSON.parse(raw) : {};
      if (!response.ok) {
        const message =
          isRecord(parsed) && typeof parsed.error === "string"
            ? parsed.error
            : `RAG service responded ${response.status}`;
        throw new RagServiceError(message, response.status);
      }
      return parsed as T;
    } catch (error) {
      // A real backend error (non-2xx) is final; only connection failures retry.
      if (error instanceof RagServiceError) throw error;
      lastError = error;
      if (Date.now() > deadline) break;
      await delay(300);
    }
  }

  throw new RagServiceError(
    `Could not reach the RAG sidecar at ${base}. Start it with \`bun run dev\` ` +
      `(or \`bun run dev:rag\`). Last error: ${String(lastError)}`,
    503,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function toServiceError(error: unknown): {
  error: string;
  status: number;
} {
  if (error instanceof RagServiceError) {
    return { error: error.message, status: error.status };
  }
  return {
    error: error instanceof Error ? error.message : String(error),
    status: 500,
  };
}
