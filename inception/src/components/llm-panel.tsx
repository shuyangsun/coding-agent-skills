import { useState } from "react";
import { ChevronDown } from "lucide-react";

import type { LlmSettings, LlmTarget } from "#/types/rag";
import { cn } from "#/lib/format";
import { LLM_PRESETS } from "#/lib/settings";
import { Field, Segmented, TextArea, TextInput } from "#/components/ui";

type Props = {
  settings: LlmSettings;
  onChange: (next: LlmSettings) => void;
};

const TARGET_OPTIONS: Array<{
  value: LlmTarget;
  label: string;
  title: string;
}> = [
  {
    value: "local",
    label: LLM_PRESETS.local.label,
    title: "An OpenAI-compatible endpoint on this machine",
  },
  {
    value: "cloud",
    label: LLM_PRESETS.cloud.label,
    title: "The remote OpenAI-compatible endpoint",
  },
];

export function LlmPanel({ settings, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const set = <K extends keyof LlmSettings>(key: K, value: LlmSettings[K]) =>
    onChange({ ...settings, [key]: value });
  const modelMissing = settings.model.trim().length === 0;

  return (
    <div className="flex flex-col gap-4">
      <Field label="Endpoint">
        <Segmented<LlmTarget>
          ariaLabel="LLM endpoint"
          className="w-full"
          value={settings.target}
          onChange={(target) =>
            onChange({
              ...settings,
              target,
              baseUrl: LLM_PRESETS[target].baseUrl,
            })
          }
          options={TARGET_OPTIONS.map((option) => ({
            ...option,
            label: <span className="flex-1">{option.label}</span>,
          }))}
        />
      </Field>

      <Field label="Base URL">
        <TextInput
          value={settings.baseUrl}
          spellCheck={false}
          autoCapitalize="off"
          onChange={(event) => set("baseUrl", event.target.value)}
          placeholder="http://127.0.0.1:8085/v1"
          className="font-mono text-xs"
        />
      </Field>

      <Field
        label="Model"
        hint={
          modelMissing ? <span className="text-danger">required</span> : null
        }
      >
        <TextInput
          value={settings.model}
          spellCheck={false}
          autoCapitalize="off"
          onChange={(event) => set("model", event.target.value)}
          placeholder="e.g. model, gemma-4, gpt-4o-mini"
          className={cn(
            "font-mono text-xs",
            modelMissing && "border-danger/50",
          )}
        />
      </Field>

      <Field label="API key" hint="optional · stored locally">
        <TextInput
          type="password"
          value={settings.apiKey}
          spellCheck={false}
          autoComplete="off"
          onChange={(event) => set("apiKey", event.target.value)}
          placeholder="Bearer token (if the endpoint needs one)"
          className="font-mono text-xs"
        />
      </Field>

      <div className="border-t border-edge pt-1">
        <button
          type="button"
          onClick={() => setAdvancedOpen((open) => !open)}
          className="flex w-full items-center justify-between py-1 text-xs font-medium text-muted transition hover:text-fg"
          aria-expanded={advancedOpen}
        >
          Advanced
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform",
              advancedOpen && "rotate-180",
            )}
          />
        </button>

        {advancedOpen ? (
          <div className="mt-3 flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Temperature">
                <TextInput
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={settings.temperature}
                  onChange={(event) =>
                    set("temperature", clamp(event.target.value, 0, 2, 0.2))
                  }
                />
              </Field>
              <Field label="Max tokens">
                <TextInput
                  type="number"
                  min={1}
                  step={50}
                  value={settings.maxTokens}
                  onChange={(event) =>
                    set(
                      "maxTokens",
                      Math.round(clamp(event.target.value, 1, 100000, 16384)),
                    )
                  }
                />
              </Field>
            </div>
            <Field label="Max context chars">
              <TextInput
                type="number"
                min={500}
                step={500}
                value={settings.maxContextChars}
                onChange={(event) =>
                  set(
                    "maxContextChars",
                    Math.round(clamp(event.target.value, 500, 200000, 12000)),
                  )
                }
              />
            </Field>
            <Field label="System prompt" hint="blank = default">
              <TextArea
                rows={4}
                value={settings.systemPrompt}
                onChange={(event) => set("systemPrompt", event.target.value)}
                placeholder="Answer only from the provided context. Cite sources like [1]…"
                className="text-xs"
              />
            </Field>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function clamp(
  raw: string,
  min: number,
  max: number,
  fallback: number,
): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}
