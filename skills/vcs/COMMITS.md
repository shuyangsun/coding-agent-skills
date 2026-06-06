# Commits

Use this format **every time you create or edit a commit message**, in any version-control system. No exceptions, including merge commits and rewrites you author.

## Format

```text
type(scope): subject under ~70 chars, imperative mood, no trailing period

Optional body wrapped at ~72 chars. Explain WHY the change exists and any
non-obvious tradeoff — not WHAT changed (the diff shows that). Skip the
body only for trivial one-liners (typo fixes, dep bumps, config tweaks).

Co-Authored-By: <Model Name> <noreply-email>
```

- **type**: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `style`, `build`, `ci`.
- **scope**: short area tag matching the codebase (`picker`, `consent`, `langfuse`, `setup`, `plan`, …). Skip parens if no natural scope.
- **subject**: imperative ("add", "fix", "route"), lowercase after the colon, no period.
- **body**: present only when it adds signal a reader can't get from the diff (motivation, constraint, follow-up). Never restate the file list.

## Co-Authored-By trailer (LLM agents)

If you are an LLM agent **and** your tool/model has a known no-reply GitHub email, append a `Co-Authored-By` trailer naming **both the model and the coding-agent tool**. One blank line before the trailer block; no blank lines between multiple trailers.

Known identities:

| Agent / tool             | Trailer                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Claude Code CLI          | `Co-Authored-By: Claude <model name and version> (Claude Code) <noreply@anthropic.com>`                       |
| Cursor agent             | `Co-Authored-By: <model name and version> (Cursor) <cursoragent@cursor.com>`                                  |
| Codex CLI / Cloud        | `Co-Authored-By: <model name and version> (Codex) <codex@openai.com>`                                         |
| Gemini CLI / Antigravity | `Co-Authored-By: <model name and version> (<Gemini CLI / Antigravity>) <your verified GitHub no-reply email>` |

Examples (substitute the actual model you're running):

```text
Co-Authored-By: Claude Opus 4.7 (1M context) (Claude Code) <noreply@anthropic.com>
Co-Authored-By: Composer 2.5 (Cursor) <cursoragent@cursor.com>
Co-Authored-By: GPT-5.5 Codex (Codex CLI) <codex@openai.com>
Co-Authored-By: Gemini 3.5 Flash (Antigravity) <your verified GitHub no-reply email>
```

For Gemini CLI / Antigravity, fill in your tool's verified GitHub no-reply email (the `<id>+<account>@users.noreply.github.com` address tied to its GitHub account) so the commit links back to that agent. If you don't know your tool's no-reply email, **omit the trailer** rather than invent one. Human co-authors use their real GitHub email on their own line.

## Examples

Good — feature with motivation:

```text
feat(picker): equal cookie sizes, aligned baseline, mobile shrink

Make the three cookie choices visually equal and aligned on both
desktop and mobile, and let the hero illustration dominate on phones
again (cookies were taking most of the viewport).

Co-Authored-By: Claude Opus 4.7 (1M context) (Claude Code) <noreply@anthropic.com>
```

Good — trivial change, no body needed:

```text
chore(setup): export local auth env vars
```

Bad — vague subject, no scope, no WHY:

```text
update stuff
fix bug
```

## Mechanics

- Pass the message via a HEREDOC so the blank lines and the trailer survive intact, whatever VCS you're using:

```sh
<commit command> -m "$(cat <<'EOF'
chore(setup): migrate repo workflow

Explain why the workflow moved and any non-obvious constraints.

Co-Authored-By: GPT-5.1 Codex (Codex) <codex@openai.com>
EOF
)"
```

- Never edit someone else's existing commit just to graft a trailer onto it; author a new commit instead.
