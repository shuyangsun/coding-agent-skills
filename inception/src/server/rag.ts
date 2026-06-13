import { createServerFn } from "@tanstack/react-start";

import type {
  AnswerOutcome,
  AnswerResult,
  Kind,
  Project,
  QueryOutcome,
  QueryResult,
} from "#/types/rag";
import { ragFetch, toServiceError } from "./rag-service";

export const listProjects = createServerFn({ method: "GET" }).handler(
  async (): Promise<Project[]> => {
    const data = await ragFetch<{ projects: Project[] }>("/projects");
    return data.projects;
  },
);

type QueryInput = {
  query: string;
  project: string;
  kind: Kind;
  topK: number;
  rerank: boolean;
};

export const runQuery = createServerFn({ method: "POST" })
  .validator((data: QueryInput) => data)
  .handler(async ({ data }): Promise<QueryOutcome> => {
    try {
      const started = Date.now();
      const result = await ragFetch<Omit<QueryResult, "ms">>("/query", {
        method: "POST",
        body: {
          query: data.query,
          project: data.project,
          kind: data.kind,
          top_k: data.topK,
          rerank: data.rerank,
        },
      });
      return { ok: true, data: { ...result, ms: Date.now() - started } };
    } catch (error) {
      return { ok: false, ...toServiceError(error) };
    }
  });

type AnswerInput = QueryInput & {
  baseUrl: string;
  model: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
  maxContextChars: number;
  systemPrompt: string;
};

export const runAnswer = createServerFn({ method: "POST" })
  .validator((data: AnswerInput) => data)
  .handler(async ({ data }): Promise<AnswerOutcome> => {
    try {
      const started = Date.now();
      const result = await ragFetch<Omit<AnswerResult, "ms">>("/answer", {
        method: "POST",
        body: {
          query: data.query,
          project: data.project,
          kind: data.kind,
          top_k: data.topK,
          rerank: data.rerank,
          model: data.model,
          base_url: data.baseUrl,
          api_key: data.apiKey || undefined,
          temperature: data.temperature,
          max_tokens: data.maxTokens,
          max_context_chars: data.maxContextChars,
          system_prompt: data.systemPrompt || undefined,
        },
      });
      return { ok: true, data: { ...result, ms: Date.now() - started } };
    } catch (error) {
      return { ok: false, ...toServiceError(error) };
    }
  });
