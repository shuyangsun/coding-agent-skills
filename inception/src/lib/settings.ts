import { useEffect, useState } from "react";

import type { LlmSettings, LlmTarget } from "#/types/rag";

export const LLM_PRESETS: Record<
  LlmTarget,
  { label: string; baseUrl: string }
> = {
  local: { label: "Local", baseUrl: "http://127.0.0.1:8000/v1" },
  cloud: { label: "Cloud", baseUrl: "https://llm.shuyangsun.com/v1" },
};

export const DEFAULT_LLM: LlmSettings = {
  target: "local",
  baseUrl: LLM_PRESETS.local.baseUrl,
  model: "",
  apiKey: "",
  temperature: 0.2,
  maxTokens: 16384,
  maxContextChars: 12000,
  systemPrompt: "",
};

export const LLM_STORAGE_KEY = "inception-llm";

/**
 * State persisted to localStorage. SSR renders `initial`; the first client paint
 * also renders `initial` (no localStorage on the server), then a mount effect
 * hydrates from storage — this ordering avoids a hydration mismatch. Updates go
 * through the returned setter, which writes storage immediately (so the mount
 * effect never races a stale write).
 */
export function usePersistentState<T extends object>(
  key: string,
  initial: T,
): [T, (next: T) => void] {
  const [state, setState] = useState<T>(initial);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<T>;
        setState((prev) => ({ ...prev, ...parsed }));
      }
    } catch {
      // ignore unreadable/corrupt storage
    }
  }, [key]);

  const update = (next: T) => {
    setState(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // ignore storage-disabled
    }
  };

  return [state, update];
}
