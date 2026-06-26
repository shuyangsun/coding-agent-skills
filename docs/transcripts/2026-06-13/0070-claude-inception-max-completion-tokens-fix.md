---
title: "Inception: fix OpenAI `max_tokens` unsupported-parameter error"
date: 2026-06-13
repo: "coding-agent-skills (change `qnlnsxswrnlq`, parent `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  The Inception RAG service always sent `max_tokens` to the OpenAI-compatible chat
  endpoint; newer OpenAI models reject it and require `max_completion_tokens`. Added a
  one-shot retry in `_call_llm` that renames the field only when the provider asks for it,
  so local (gemma) endpoints keep working.
---

<!-- markdownlint-disable MD013 MD024 -->

# Inception: fix OpenAI `max_tokens` unsupported-parameter error

## User

For @inception/, when I use OpenAI API, I get error:

```text
provider returned HTTP 400: { "error": { "message": "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", "type": "invalid_request_error", "param": "max_tokens", "code": "unsupported_parameter" } }
```

Fix it.

## Assistant

Searched for `max_tokens` usage across `inception/src` and `inception/rag-service`. Found three sites:

- `src/server/rag.ts:76` — forwards `max_tokens: data.maxTokens` to the RAG service.
- `rag-service/serve.py:338` — reads `max_tokens` from the request body / config.
- `rag-service/serve.py:366` — places `max_tokens` into the outbound chat-completions request body.

Read `_call_llm` (`serve.py:187`) — the actual HTTP call to the OpenAI-compatible provider. The provider returns the 400; the field is hardcoded as `max_tokens`. Because the local gemma endpoint only understands `max_tokens`, the field can't be renamed unconditionally — instead the call should retry with `max_completion_tokens` when (and only when) the provider rejects `max_tokens`.

Edited `_call_llm` to build the request inside the `try` block and catch the specific 400:

```python
except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")[:800]
    # Newer OpenAI models reject 'max_tokens' and require
    # 'max_completion_tokens'. Retry once with the renamed field.
    if (
        exc.code == 400
        and "max_tokens" in body
        and "max_completion_tokens" in detail
    ):
        retry_body = {
            k: v for k, v in body.items() if k != "max_tokens"
        }
        retry_body["max_completion_tokens"] = body["max_tokens"]
        return _call_llm(
            base_url=base_url,
            api_key=api_key,
            body=retry_body,
            timeout=timeout,
        )
    raise ApiError(f"provider returned HTTP {exc.code}: {detail}", 502) from exc
```

Syntax-checked with `ast.parse` (ok) and confirmed the change is tracked by jj (`M inception/rag-service/serve.py`).

**What was wrong:** the OpenAI-compatible call always sent `max_tokens`; newer OpenAI models (o1, gpt-5, etc.) reject it and require `max_completion_tokens`, producing the HTTP 400. The local gemma endpoint only understands `max_tokens`, so a blanket rename would break it.

**The fix:** `_call_llm` now catches the specific 400, and if the provider's message names `max_completion_tokens`, retries once with the field renamed. Local endpoints are unaffected; newer OpenAI models succeed on the retry.

## User

Export session transcript, integrate with /vcs

## Assistant

Exported this transcript via the `export-transcript` skill to `docs/transcripts/2026-06-13/0070-claude-inception-max-completion-tokens-fix.md`, ran the redaction scan, then handed off to the `vcs` skill to commit the work.
