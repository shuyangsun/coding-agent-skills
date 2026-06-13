// Shared RAG types. Wire shapes (Project, RetrievalHit, AnswerSource, *Response)
// mirror the sidecar's JSON verbatim, so they keep snake_case; app-only types
// (RetrievalParams, LlmSettings, SearchState) use camelCase.

export const KINDS = ["all", "md", "code"] as const;
export type Kind = (typeof KINDS)[number];

// --- wire shapes (from rag-service/serve.py) --------------------------------
export type ProjectCollection = {
  kind: string;
  collection: string | null;
  chunk_count: number;
  source_count: number;
  indexed_at: string | null;
};

export type Project = {
  key: string;
  name: string;
  root: string;
  collections: ProjectCollection[];
  total_chunks: number;
  total_sources: number;
};

export type RetrievalHit = {
  project: string | null;
  kind: string | null;
  collection: string;
  doc_id: string | null;
  chunk_idx: number | null;
  score: number;
  text: string;
};

export type AnswerSource = {
  source_id: number;
  doc_id: string;
  chunk_idx: number | null;
  score: number;
  text: string;
  collection: string;
  project: string | null;
  kind: string | null;
};

export type Usage = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
} | null;

export type QueryResult = {
  results: RetrievalHit[];
  where: string;
  target: string;
  ms: number;
};

export type AnswerResult = {
  answer: string;
  sources: AnswerSource[];
  usage: Usage;
  model: string;
  base_url: string;
  where: string;
  target: string;
  ms: number;
};

// Server functions return an outcome (never throw across the boundary) so the
// real backend error text always reaches the UI.
export type Outcome<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status: number };
export type QueryOutcome = Outcome<QueryResult>;
export type AnswerOutcome = Outcome<AnswerResult>;

// --- app-side params --------------------------------------------------------
export type RetrievalParams = {
  query: string;
  project: string;
  kind: Kind;
  topK: number;
  rerank: boolean;
};

export type SearchMode = "retrieve" | "answer";

export type LlmTarget = "local" | "cloud";

export type LlmSettings = {
  target: LlmTarget;
  baseUrl: string;
  model: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
  maxContextChars: number;
  systemPrompt: string;
};

// --- search action state (discriminated union) ------------------------------
export type SearchState =
  | { status: "idle" }
  | { status: "retrieved"; data: QueryResult }
  | { status: "answered"; data: AnswerResult }
  | { status: "error"; message: string };

export function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}
