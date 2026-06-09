# RAG eval set — `website`

- **Repo root:** `/Users/shuyang/developer/website`
- **Questions:** 43  ·  domain {'code': 23, 'nl': 20}  ·  difficulty {'easy': 7, 'hard': 9, 'medium': 27}  ·  source {'claude': 28, 'codex': 15}
- **Code corpus (`domain=code`):** shuyang-website/src/ + config (Vite + React + TanStack + Cloudflare Worker), tools/, scripts/
- **Prose corpus (`domain=nl`):** llm-sessions-history/ (exported transcripts), prompts/, docs/{design,plan,research}
- **Note:** Personal website (Cloudflare Worker app) with exported session transcripts, so the set splits codebase vs prompting/session-history.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (23)

### web-vite-phaser-prebundle-exclude

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** In the website's Vite build, the WebGL/Canvas figure renderer library is deliberately kept out of the dependency pre-bundling step. Which library is excluded and through what config option, and why does the comment say this matters for SSR and code-splitting?
- **A:** vite.config.ts sets optimizeDeps: { exclude: ['phaser'] } so Vite does not eagerly prebundle Phaser; because Phaser touches window/document at module top-level and is only ever imported via a client-side dynamic import inside a React effect, excluding it keeps the SSR bundle from executing its body and lets the import code-split cleanly.
- **sentinels:** `optimizeDeps: { exclude: ['phaser'] }`
- **primary:** `shuyang-website/vite.config.ts`
- **evidence:** shuyang-website/vite.config.ts:26:  optimizeDeps: { exclude: ['phaser'] },

### web-react-compiler-babel-before-vitereact

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The site runs the React Compiler 1.0 even though the React Vite plugin v6 dropped Babel. How is the compiler wired into the plugin pipeline, and what ordering constraint relative to the React plugin must hold for it to work?
- **A:** vite.config.ts runs the compiler via @rolldown/plugin-babel using babel({ presets: [reactCompilerPreset()] }), and that babel plugin MUST sit before viteReact() so the compiler sees component/hook source before JSX is transformed.
- **sentinels:** `reactCompilerPreset()`, `@rolldown/plugin-babel`
- **primary:** `shuyang-website/vite.config.ts`
- **evidence:** shuyang-website/vite.config.ts:33:    babel({ presets: [reactCompilerPreset()] }), ; :7:import babel from '@rolldown/plugin-babel' ; :31:// the compiler runs via @rolldown/plugin-babel and MUST sit before viteReact()

### web-dev-boot-id-consent-storage-scope

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How does the dev server force the cookie picker to reappear on every restart even if the same browser tab stays open, and how is the value that makes this work generated at build/boot time and threaded into the consent storage key?
- **A:** vite.config.ts computes a fresh per-boot id with `b${Date.now().toString(36)}`, injects it via define as __DEV_BOOT_ID__, and consent.tsx folds it into RUNTIME_STORAGE_KEY (using sessionStorage in dev) so a vite dev restart changes the key and wipes the previous tier; prod uses the stable key in localStorage instead.
- **sentinels:** `Date.now().toString(36)`, `__DEV_BOOT_ID__`, `RUNTIME_STORAGE_KEY`
- **primary:** `shuyang-website/vite.config.ts`, `shuyang-website/src/lib/consent.tsx`
- **evidence:** shuyang-website/vite.config.ts:14:const DEV_BOOT_ID = `b${Date.now().toString(36)}` ; :19:    __DEV_BOOT_ID__: JSON.stringify(DEV_BOOT_ID), ; shuyang-website/src/lib/consent.tsx:22:export const RUNTIME_STORAGE_KEY = import.meta.env.DEV ? `${CONSENT_STORAGE_KEY}:dev:${DEV_BOOT_ID}` : CONSENT_STORAGE_KEY ; :27:  return import.meta.env.DEV ? window.sessionStorage : window.localStorage

### web-figure-align-seated-base-anchor

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When crossfading the hero poses, what part of the silhouette is used as the registration anchor (rather than the whole figure's centroid), what fraction of the figure height defines that anchoring band, and what residual measurement slides the printed shirt text on the leaning pose?
- **A:** figure-align.ts anchors on the seated base (legs/seat footprint) using a band BASE_BAND_FRAC = 0.12 of the figure height measured up from the baseline, because a raised cup yanks the overall centroid sideways; registerPrintShift then measures how far the leaning pose's chest sits off the resting chest so the shirt print can be slid back onto the fabric.
- **sentinels:** `BASE_BAND_FRAC = 0.12`, `registerPrintShift`
- **primary:** `shuyang-website/src/lib/figure-align.ts`
- **evidence:** shuyang-website/src/lib/figure-align.ts:30:const BASE_BAND_FRAC = 0.12 ; :28:// Fraction of the figure's height, measured up from the baseline, that defines the "seated base" band ; :212:export function registerPrintShift(

### web-provider-race-cancels-slower

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When the worker generates shirt text it fires multiple LLM providers in parallel. Once one returns usable text, how does the racing logic treat the still-pending providers, and which span names distinguish the no-cookie direct call from the gateway call?
- **A:** raceThoughtProviders resolves on the first attempt whose exchange is ok with output, then loops the remaining pending candidates and calls slowerCandidate.abort() to cancel them; the no-cookie (ConsentTier.None) GCP path uses the span name 'gcp.maas.direct' while the gateway path uses 'cf.aig.request'.
- **sentinels:** `slowerCandidate.abort()`, `gcp.maas.direct`, `cf.aig.request`
- **primary:** `shuyang-website/src/lib/generate-shirt-thought.ts`
- **evidence:** shuyang-website/src/lib/generate-shirt-thought.ts:1291:        slowerCandidate.abort() ; :1203:        spanName: 'gcp.maas.direct', ; :1214:        spanName: 'cf.aig.request', ; :1258:export async function raceThoughtProviders(

### web-consent-tier-gateway-log-headers

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** For the gateway-routed shirt-thought call, how does the consent tier change AI Gateway logging behavior, and which observability profile does the 'essential' tier map to?
- **A:** getObservabilityProfile maps the essential tier to ObservabilityProfile.MetricsOnly, and when logs aren't collected the gateway request sets the headers cf-aig-collect-log to 'false' (and cf-aig-collect-log-payload to 'false'), so essential gets metrics-only Langfuse on the winner with gateway log payloads disabled.
- **sentinels:** `ObservabilityProfile.MetricsOnly`, `cf-aig-collect-log`
- **primary:** `shuyang-website/src/lib/generate-shirt-thought.ts`
- **evidence:** shuyang-website/src/lib/generate-shirt-thought.ts:172:    return ObservabilityProfile.MetricsOnly ; :171:  if (consent === ConsentTier.Essential) ; :949:    headers.set('cf-aig-collect-log', 'false') ; :950:    headers.set('cf-aig-collect-log-payload', 'false')

### web-inner-thought-throttle-unfinished-sentence

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The server-side throttle on ambient inner-thought generation imposes a longer required idle delay for prompts that look mid-sentence. How does it decide a prompt is unfinished, and what idle delay does that trigger under the normal profile?
- **A:** inner-thought-throttle.server.ts treats a prompt as unfinished when it has at least UNFINISHED_SENTENCE_MIN_WORDS = 6 words and does not end in sentence-ending punctuation, and isUnfinishedSentence then selects the Normal profile's unfinishedSentenceDelayMs: 1500 required idle window instead of the shorter base delay.
- **sentinels:** `UNFINISHED_SENTENCE_MIN_WORDS = 6`, `unfinishedSentenceDelayMs: 1500`, `isUnfinishedSentence`
- **primary:** `shuyang-website/src/lib/inner-thought-throttle.server.ts`
- **evidence:** shuyang-website/src/lib/inner-thought-throttle.server.ts:31:const UNFINISHED_SENTENCE_MIN_WORDS = 6 ; :37:    unfinishedSentenceDelayMs: 1500, ; :48:function isUnfinishedSentence(prompt: string) ; :52:words.length >= UNFINISHED_SENTENCE_MIN_WORDS && !SENTENCE_END_RE.test(normalized)

### web-avatar-route-etag-304

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the avatar image worker route avoid resending a cached portrait body, and what cache-control header value does it apply to served avatars?
- **A:** The /avatar/$ route validates the splat with isAvatarObjectKey, then compares the request's If-None-Match header against the R2 object's httpEtag and returns a 304 with no body when they match; otherwise it serves the body with AVATAR_CACHE_CONTROL = 'public, max-age=31536000, immutable'.
- **sentinels:** `If-None-Match`, `public, max-age=31536000, immutable`, `isAvatarObjectKey`
- **primary:** `shuyang-website/src/routes/avatar.$.ts`
- **evidence:** shuyang-website/src/routes/avatar.$.ts:32:        if (request.headers.get('If-None-Match') === object.httpEtag) ; :4:const AVATAR_CACHE_CONTROL = 'public, max-age=31536000, immutable' ; :18:if (!bucket \|\| !key \|\| !isAvatarObjectKey(key))

### web-avatar-object-key-format

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** What is the structure of the R2 object key used to cache a signed-in visitor's generated portrait, including how the picture-category and the dated style version are encoded into it?
- **A:** buildAvatarObjectKey produces a key like avatar-portraits/v1/{userIdHash}/{photoHash}-{alias}-{HERO_STYLE_VERSION}-{promptVersion}.png, where the category alias comes from AVATAR_CATEGORY_ALIASES (real/art/none) and the dated style segment is HERO_STYLE_VERSION = '2026-05'; isAvatarObjectKey validates this against AVATAR_OBJECT_KEY_PATTERN.
- **sentinels:** `AVATAR_CATEGORY_ALIASES`, `HERO_STYLE_VERSION = '2026-05'`, `AVATAR_OBJECT_KEY_PATTERN`
- **primary:** `shuyang-website/src/lib/avatar-portrait-helpers.ts`
- **evidence:** shuyang-website/src/lib/avatar-portrait-helpers.ts:12:export const HERO_STYLE_VERSION = '2026-05' ; :20:export const AVATAR_CATEGORY_ALIASES = { ... 'real'/'art'/'none' ; :26:export const AVATAR_OBJECT_KEY_PREFIX = 'avatar-portraits' ; :76:return `${AVATAR_OBJECT_KEY_PREFIX}/v1/${userIdHash}/${photoHash}-${categoryAlias}-${HERO_STYLE_VERSION}-${promptVersion}.png` ; :45:const AVATAR_OBJECT_KEY_PATTERN =

### web-avatar-mime-magic-bytes

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** Beyond trusting the declared content type, how does the avatar helper detect an uploaded image's real format, and what byte signature does it check to recognize a WebP?
- **A:** detectAvatarImageMimeType first normalizes the declared content type and, failing that, sniffs magic bytes: for WebP it requires the RIFF header (bytes 0x52 'R', 0x49, 0x46, 0x46) plus the 'WEBP' marker at offset 8, and similarly checks signatures for JPEG, PNG, and GIF.
- **sentinels:** `detectAvatarImageMimeType`, `0x52`
- **primary:** `shuyang-website/src/lib/avatar-portrait-helpers.ts`
- **evidence:** shuyang-website/src/lib/avatar-portrait-helpers.ts:153:export function detectAvatarImageMimeType( ; :162:      bytes[0] === 0x52 &&

### web-provider-token-cookie-chunking

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** Because a signed provider token can exceed a single cookie's size, how does the auth layer store it across cookies, what per-cookie chunk size does it use, and what is the maximum number of chunks?
- **A:** auth-provider-cookies.ts splits the signed token into pieces of PROVIDER_TOKEN_CHUNK_SIZE = 3000 chars stored as numbered shuyang_provider_N cookies, writes the chunk count into the base cookie, and caps the total at MAX_PROVIDER_TOKEN_CHUNKS = 8, clearing the remaining slots when fewer are needed.
- **sentinels:** `PROVIDER_TOKEN_CHUNK_SIZE = 3000`, `MAX_PROVIDER_TOKEN_CHUNKS = 8`
- **primary:** `shuyang-website/src/lib/auth-provider-cookies.ts`
- **evidence:** shuyang-website/src/lib/auth-provider-cookies.ts:6:const PROVIDER_TOKEN_CHUNK_SIZE = 3000 ; :7:const MAX_PROVIDER_TOKEN_CHUNKS = 8 ; :4:const PROVIDER_TOKEN_COOKIE_NAME = 'shuyang_provider' ; :50:function providerTokenChunkName(index) returns `${PROVIDER_TOKEN_CHUNK_PREFIX}${index}`

### web-github-mirror-sync-markdown-tree

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When the offline GitHub mirror sync collects every Markdown file from an allowlisted repo, which GitHub API call lists the files, how does it guard against incomplete listings, and which API-version header does it send?
- **A:** sync.ts lists files by calling the git/trees/{branch}?recursive=1 endpoint, and if the response has truncated === true it logs and bails (returns null) so an incomplete listing isn't mirrored; every GitHub request sends the X-GitHub-Api-Version header (GITHUB_API_VERSION '2022-11-28').
- **sentinels:** `git/trees/`, `truncated === true`, `X-GitHub-Api-Version`
- **primary:** `tools/github-mirror/sync.ts`
- **evidence:** tools/github-mirror/sync.ts:297:    `/repos/${owner}/${repo}/git/trees/${branch}?recursive=1`, ; :312:  if (record.truncated === true) { ; :316:    return null; ; :198:        "X-GitHub-Api-Version": GITHUB_API_VERSION, ; :29:const GITHUB_API_VERSION = "2022-11-28";

### web-repo-key-derivation

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** How does the GitHub mirror derive the stable per-repo key used in R2 object paths from an owner and repo name, and what separator and casing does it apply?
- **A:** createRepoKey validates the owner and repo against the GitHub name patterns and returns a lowercased key joined by a double-dash, `${normalizedOwner.toLowerCase()}--${normalizedRepo.toLowerCase()}`, returning null when either part is invalid.
- **sentinels:** `createRepoKey`, `${normalizedOwner.toLowerCase()}--${normalizedRepo.toLowerCase()}`
- **primary:** `shuyang-website/src/lib/github-mirror.ts`
- **evidence:** shuyang-website/src/lib/github-mirror.ts:98:export function createRepoKey(owner: string, repo: string): string \| null { ; :104:  return `${normalizedOwner.toLowerCase()}--${normalizedRepo.toLowerCase()}`

### web-ssim-locked-region-skip

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the art-pipeline scoring, how does the windowed SSIM metric avoid measuring areas that were intentionally edited, and what window size and stride does it use?
- **A:** ssim.ts's meanSsim scans 8x8 windows (WINDOW = 8) at stride 4 with the standard C1/C2 stabilizers, and skips any window where the edit mask is set (skip[idx] > 0.1), so it scores only the region meant to stay locked and returns the mean SSIM over the scored windows.
- **sentinels:** `meanSsim`, `WINDOW = 8`, `skip[idx] > 0.1`
- **primary:** `tools/art-pipeline/src/scoring/ssim.ts`
- **evidence:** tools/art-pipeline/src/scoring/ssim.ts:10:export function meanSsim( ; :5:const WINDOW = 8 ; :30:          if (skip && skip[idx] > 0.1) {

### web-shirt-text-arm-collision

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the typeable t-shirt component decide that the typed words have run into the figure's forearm, mapping the offline-derived geometry into the laid-out text box?
- **A:** shirt-text.tsx measures the unwrapped ink width with pretext and computes the forearm's left edge in content space via (arm.edge_x - print.x) * frameW - padL, then fires the collision when text.trim().length > 0 && measureNaturalWidth(prepared) > armX, which the parent uses to lift the cup away.
- **sentinels:** `arm.edge_x - print.x`, `measureNaturalWidth(prepared) > armX`
- **primary:** `shuyang-website/src/components/shirt-text.tsx`
- **evidence:** shuyang-website/src/components/shirt-text.tsx:117:      const armX = (arm.edge_x - print.x) * frameW - padL ; :119:        text.trim().length > 0 && measureNaturalWidth(prepared) > armX,

### web-eslint-ban-manual-memo-enums

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** The project's ESLint config hard-bans certain React and TypeScript constructs via no-restricted-syntax. Which memoization patterns and which TypeScript declaration are rejected, and why?
- **A:** eslint.config.js's no-restricted-syntax rule errors on manual useMemo/useCallback and React.memo with the message 'No manual memoization. The React Compiler memoizes automatically…', and also bans TSEnumDeclaration (TS enums) in favor of a const object plus union type because enums are not erasable.
- **sentinels:** `No manual memoization`, `TSEnumDeclaration`
- **primary:** `shuyang-website/eslint.config.js`
- **evidence:** shuyang-website/eslint.config.js:35:'No manual memoization. The React Compiler memoizes automatically — delete useMemo/useCallback and let the compiler do it.', ; :44:          selector: 'TSEnumDeclaration',

### web-aisearch-reranker-threshold-clamp

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the server-only writing-corpus search wrapper, after fusion and keyword matching the candidates are reordered by a second-stage model and filtered by a default score cutoff. Which cross-encoder reordering model and which default score cutoff does it use, and within what bounds is the requested result count constrained?
- **A:** searchWritingCorpus reranks with the model '@cf/baai/bge-reranker-base', applies a default match threshold of 0.4 (DEFAULT_MATCH_THRESHOLD), and clamps the requested max results to between 1 and 50 via Math.max(1, Math.min(50, Math.trunc(value))).
- **sentinels:** `@cf/baai/bge-reranker-base`, `DEFAULT_MATCH_THRESHOLD = 0.4`, `Math.max(1, Math.min(50, Math.trunc(value)))`
- **primary:** `shuyang-website/src/lib/retrieval.server.ts`
- **evidence:** shuyang-website/src/lib/retrieval.server.ts:12:const DEFAULT_RERANKER_MODEL = '@cf/baai/bge-reranker-base' ; :11:const DEFAULT_MATCH_THRESHOLD = 0.4 ; :23:  return Math.max(1, Math.min(50, Math.trunc(value)))

### web-github-search-route-dev-only-404

- **slice:** codebase · **difficulty:** easy · **source:** codex
- **Q:** The exploratory corpus-search HTTP endpoint is meant to be a temporary local diagnostic. How does the route handler ensure it cannot be reached from a production deployment?
- **A:** The /github/search GET handler checks the dev build flag first and, when not in dev (if (!import.meta.env.DEV)), immediately returns a 404 'not found' Response, so the search endpoint only works in Vite dev mode.
- **sentinels:** `if (!import.meta.env.DEV)`, `createFileRoute('/github/search')`
- **primary:** `shuyang-website/src/routes/github.search.ts`
- **evidence:** shuyang-website/src/routes/github.search.ts:16:        if (!import.meta.env.DEV) { ; :17:          return new Response('not found', { status: 404 }) ; :12:export const Route = createFileRoute('/github/search')(

### web-retrieval-mirror-key-to-github-blob-url

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** When an AI Search result item points at a mirrored markdown object, how does the pure retrieval-normalizer turn that storage key into a clickable GitHub citation URL, and which ref does the constructed permalink point at?
- **A:** sourceFromAiSearchKey strips the mirror repos prefix to recover the repo key and relative path, then githubUrlFromMirror splits the repo key on '--' into owner and repo and builds a URL of the form https://github.com/{owner}/{repo}/blob/HEAD/{encoded path}, i.e. it cites the HEAD ref.
- **sentinels:** `githubUrlFromMirror`, `blob/HEAD/`, `GITHUB_MIRROR_REPO_PREFIX`
- **primary:** `shuyang-website/src/lib/retrieval.ts`
- **evidence:** shuyang-website/src/lib/retrieval.ts:83:function githubUrlFromMirror(repoKey: string, path: string): string \| null { ; :93:  )}/blob/HEAD/${encodeGithubPath(path)}` ; :9:const GITHUB_MIRROR_REPO_PREFIX = `${GITHUB_MIRROR_PREFIX}/repos/`

### web-feature-flag-userhash-cache-failclosed

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When the Worker resolves a signed-in visitor's feature flags, how is the user identity turned into the R2 override-lookup key, how long is the global config memoized, and what does a missing or malformed config object resolve to?
- **A:** resolveEffectiveFlags hashes the user id with sha256Hex(user.id, 16) (the first 16 hex chars of SHA-256) as the override key, memoizes the global config for GLOBAL_CONFIG_CACHE_TTL_MS = 60_000 ms, and falls back to EMPTY_GLOBAL_FLAG_CONFIG (fail-closed) whenever the R2 object is absent or malformed.
- **sentinels:** `sha256Hex(user.id, 16)`, `GLOBAL_CONFIG_CACHE_TTL_MS = 60_000`, `EMPTY_GLOBAL_FLAG_CONFIG`
- **primary:** `shuyang-website/src/lib/feature-flags.server.ts`
- **evidence:** shuyang-website/src/lib/feature-flags.server.ts:206:  const userIdHash = user ? await sha256Hex(user.id, 16) : null ; :18:const GLOBAL_CONFIG_CACHE_TTL_MS = 60_000 ; :74:    if (!object) return EMPTY_GLOBAL_FLAG_CONFIG

### web-shirt-response-mode-defaults-budget

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The shirt generator has a separate explicit-answer mode distinct from the short ambient one-liner. Which OpenAI and Google model IDs are wired as the answer-mode defaults, and how does its completion-token ceiling compare to the one-liner mode's ceiling?
- **A:** The answer (response) mode defaults to OpenAI 'gpt-5.1' and Google 'gemini-3-flash-preview', and it gets a much larger token budget: MAX_RESPONSE_COMPLETION_TOKENS = 260 versus the one-liner thought mode's MAX_THOUGHT_COMPLETION_TOKENS = 36.
- **sentinels:** `DEFAULT_OPENAI_SHIRT_RESPONSE_MODEL_ID = 'gpt-5.1'`, `DEFAULT_GCP_AP_RESPONSE_MODEL_ID = 'gemini-3-flash-preview'`, `MAX_RESPONSE_COMPLETION_TOKENS = 260`
- **primary:** `shuyang-website/src/lib/generate-shirt-thought.ts`
- **evidence:** shuyang-website/src/lib/generate-shirt-thought.ts:36:const DEFAULT_OPENAI_SHIRT_RESPONSE_MODEL_ID = 'gpt-5.1' ; :37:const DEFAULT_GCP_AP_RESPONSE_MODEL_ID = 'gemini-3-flash-preview' ; :26:const MAX_RESPONSE_COMPLETION_TOKENS = 260 ; :25:const MAX_THOUGHT_COMPLETION_TOKENS = 36

### web-readme-route-swr-index-revalidation

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** Before the mirrored-README route streams a body from R2, it re-checks that the repo is still live in the current index. What equality check guards against serving a stale README, and what caching directive does it apply to the served README?
- **A:** The /github/readme/$ handler looks up the repo in the loaded index and returns 404 unless repo?.readmeUrl !== githubReadmeUrl(repoKey) is false (i.e. the stored readmeUrl still matches the canonical one); served READMEs get Cache-Control 'public, max-age=300, stale-while-revalidate=3600'.
- **sentinels:** `readmeUrl !== githubReadmeUrl(repoKey)`, `stale-while-revalidate=3600`
- **primary:** `shuyang-website/src/routes/github.readme.$.ts`
- **evidence:** shuyang-website/src/routes/github.readme.$.ts:30:        if (repo?.readmeUrl !== githubReadmeUrl(repoKey)) { ; :8:const README_CACHE_CONTROL = 'public, max-age=300, stale-while-revalidate=3600'

### web-forearm-cutout-dom-zindex-sandwich

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** One figure layer is deliberately rendered as a DOM element rather than inside the Phaser canvas so typed shirt words can tuck under the arm. Which CSS class owns that overlay, what stacking order does it occupy relative to the resting and reacted shirt text, and why can't a single canvas do this?
- **A:** The resting forearm overlay is the .sprite-frame__cutout DOM layer at z-index 3, sitting between the resting shirt text at 2 and the reacted text at 5; a single Phaser canvas can't sandwich a DOM text element between two of its own sprites, so the cutout has to be a separate DOM layer.
- **sentinels:** `.sprite-frame__cutout {`, `between the resting text`, `z-index: 3`
- **primary:** `shuyang-website/src/styles.css`
- **evidence:** shuyang-website/src/styles.css:439:.sprite-frame__cutout { ; :442:  z-index: 3; ; :429:   the canvas: it sits ABOVE the shirt text (z-index 3, between the resting text ; :430:   at 2 and the reacted text at 5)

## `domain = nl` (20)

### web-cookie-shortbread-prompt-edge-detail

- **slice:** session-prompting · **difficulty:** easy · **source:** claude
- **Q:** In the cookie-picker image-generation prompts, how is the rim/edge of the plain shortbread (essential-tier) biscuit described so the model draws a molded look?
- **A:** The essential-tier prompt specifies a gently fluted/scalloped edge with about 14–16 shallow notches around the circumference, the way pressed shortbread comes out of a mold, plus a small docking pattern of pinprick dots near the center.
- **sentinels:** `14–16 shallow notches`, `docking pattern`
- **primary:** `prompts/20260525-cookie-picker-gen.md`
- **evidence:** prompts/20260525-cookie-picker-gen.md:48:gently fluted/scalloped (about 14–16 shallow notches around the circumference), ; :49:the way pressed shortbread comes out of a mold. A small docking pattern of

### web-hero-artifact-fix-hard-negatives

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** The revised pointing-arm asset prompt that repaints the figure where the old resting arm sat ends with a list of forbidden outputs. What does it explicitly tell the model NOT to produce regarding the arm and any phantom limb?
- **A:** The hard-negatives section of the artifact-fix prompt forbids 'No second arm behind the pointing arm', no skin-colored patch near the lap, no missing fingertip, no extra fingers, and a flat white background only (no transparent checkerboard, black circle, or grey backdrop).
- **sentinels:** `No second arm behind the pointing arm`, `No missing fingertip`
- **primary:** `prompts/20260602-hero-point-artifact-fix.md`
- **evidence:** prompts/20260602-hero-point-artifact-fix.md:40:- No second arm behind the pointing arm. ; :42:- No missing fingertip.

### web-cookie-figure-shirt-print-ink

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** For the Buddha-pose cookie-picker figure, what exact ink color and handwriting-font style does the prompt request for the chest print, and how should the ink interact with the fabric?
- **A:** The figure prompt asks for a handwritten script in the style of the Google Font Caveat at semibold weight, printed in a deep warm near-black hex #241d15 with a multiply feel so the cream fabric's shading and folds show through the ink rather than a solid pure black.
- **sentinels:** `#241d15`, `Caveat`, `multiply`
- **primary:** `prompts/20260525-cookie-picker-figure-gen.md`
- **evidence:** prompts/20260525-cookie-picker-figure-gen.md:60:- **Color.** A deep warm near-black, hex **#241d15** ; :54:- **Font.** Handwritten script in the style of the Google Font _Caveat_ ; :61:Printed with a `multiply` feel — the cream

### web-sapiens-print-surface-mask

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** In the spike validating Meta's body-part segmentation on the illustrated hero, which detected clothing class was selected as the mask for the shirt text, and why did the bare-skin torso class come back at zero percent?
- **A:** The session found the t-shirt mapped to Upper_Clothing, which became the print-surface mask, while Torso reported 0% because in the Goliath scheme Torso means bare skin and the clothed chest is classified as Upper_Clothing.
- **sentinels:** `Upper_Clothing`, `Goliath scheme`
- **primary:** `llm-sessions-history/2026-05-23/0011-claude-sapiens-shirt-text.md`
- **evidence:** llm-sessions-history/2026-05-23/0011-claude-sapiens-shirt-text.md:47:- `Torso` = **0%** — correct, because in the Goliath scheme `Torso` is _bare_ skin; on a clothed figure the chest is `Upper_Clothing`. **So `Upper_Clothing` is the print-surface mask.**

### web-gemma-e4b-neuron-budget

- **slice:** session-prompting · **difficulty:** easy · **source:** claude
- **Q:** When the production shirt-thought model was switched to Gemma 4 E4B, the session also checked the day's Workers AI neuron budget. How many neurons remained out of the free daily allowance after that check?
- **A:** The session reported 5,798 neurons remaining (about 58%) out of the 10,000 free daily allowance, with E4B mapped to @cf/google/gemma-4-26b-a4b-it until @cf/google/gemma-4-e4b-it is hosted.
- **sentinels:** `5,798`, `gemma-4-26b-a4b-it`
- **primary:** `llm-sessions-history/2026-05-24/0024-cursor-gemma-e4b-default-and-usage.md`
- **evidence:** llm-sessions-history/2026-05-24/0024-cursor-gemma-e4b-default-and-usage.md:32:\| Remaining             \| 5,798 (~58%)                                         \| ; :38:Noted E4B maps to `@cf/google/gemma-4-26b-a4b-it` until `@cf/google/gemma-4-e4b-it` is hosted.

### web-idle-nudge-pointing-timers

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** The session that wired the unused pointing artwork into the home figure as an idle prompt used two timing constants: one to trigger the pose after inactivity and one to delay reverting after the visitor first interacts. What were those two constant values?
- **A:** The idle-nudge session gated the pointing pose with POINT_IDLE_MS=3000 (three seconds after consent with no engagement) and reverted with POINT_REVERT_DELAY_MS=1000 after the first focus, kept single-shot via a shirtEngaged state.
- **sentinels:** `POINT_IDLE_MS=3000`, `POINT_REVERT_DELAY_MS=1000`
- **primary:** `llm-sessions-history/2026-05-27/0072-claude-hero-point-idle-nudge.md`
- **evidence:** llm-sessions-history/2026-05-27/0072-claude-hero-point-idle-nudge.md:1539:- `src/components/interactive-landing.tsx` — `POINT_IDLE_MS=3000` after consent gates pointing; `POINT_REVERT_DELAY_MS=1000` after first focus reverts; single-shot via `shirtEngaged` state.

### web-hidpi-canvas-scale-fix

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** After a fallback image faded and the hero figure went blurry on high-density screens, what scale-mode change fixed the resolution mismatch, and what canvas backing size did the verification record for a 390-by-487 host at a 3x device pixel ratio?
- **A:** The fix switched the Phaser scale config from Scale.RESIZE to Scale.NONE with zoom: 1/dpr so the canvas backing lives in device pixels; verification confirmed a backing of 1170×1461 for the 390×487 CSS host at a 3x device pixel ratio.
- **sentinels:** `Scale.NONE`, `1170×1461`, `zoom: 1/dpr`
- **primary:** `llm-sessions-history/2026-05-27/0078-claude-phaser-hidpi-canvas.md`
- **evidence:** llm-sessions-history/2026-05-27/0078-claude-phaser-hidpi-canvas.md:31:Switched the scale config from `Scale.RESIZE` to `Scale.NONE` with `zoom: 1/dpr` ; :41:Canvas backing = **1170×1461** for a **390×487** CSS host (exactly 3×).

### web-feature-flag-throttle-profiles

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** The feature-flag design session discovered the inner-thought timing was entirely client-side debounce, then proposed moving it server-side under a new flag. What was the test flag's name, the existing client debounce constants found, and the faster threshold proposed for the higher tier?
- **A:** The first flag was higher-inner-thought-limit; the existing client debounce constants were SHIRT_DEBOUNCE_MS = 500 and UNFINISHED_SENTENCE_MIN_WORDS = 6, and the normal profile reproduced 500/1500 ms while the proposed higher profile used 250/500 ms.
- **sentinels:** `higher-inner-thought-limit`, `UNFINISHED_SENTENCE_MIN_WORDS = 6`, `250/500 ms`
- **primary:** `llm-sessions-history/2026-06-02/0091-claude-feature-flag-system-design.md`
- **evidence:** llm-sessions-history/2026-06-02/0091-claude-feature-flag-system-design.md:29:found it's entirely client-side debounce in `src/components/thought-track.tsx`: `SHIRT_DEBOUNCE_MS = 500`, `UNFINISHED_SENTENCE_DEBOUNCE_MS = 1500`, `UNFINISHED_SENTENCE_MIN_WORDS = 6` ; :49:`normal` profile reproduces today's 500/1500 ms behavior; `higher` profile uses 250/500 ms.

### web-github-mirror-r2-sync-counts

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** When the offline GitHub Markdown mirror sync was finally run against R2, how many Markdown file objects, manifests, and README aliases did the final sync log report writing?
- **A:** The sync mirrored 4 repos and wrote 317 markdown file object(s), 4 per-repo markdown-files.json manifests, 4 readme.md aliases, and the github/v1/index.json mirror index.
- **sentinels:** `317 markdown file object(s)`, `github/v1/index.json`
- **primary:** `llm-sessions-history/2026-06-04/0102-codex-github-mirror-r2-sync-run.md`
- **evidence:** llm-sessions-history/2026-06-04/0102-codex-github-mirror-r2-sync-run.md:45:Mirroring 4 repo(s), 317 markdown file object(s), 4 README alias object(s) ; :51:- 4 per-repo `markdown-files.json` manifests ; :52:- 4 `readme.md` compatibility aliases ; :53:- `github/v1/index.json`

### web-ai-search-retrieval-bridge-config

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** The session that built the Cloudflare retrieval bridge over the GitHub Markdown mirror added a search binding and configured the server-side search call. What was the binding name, the indexed corpus name, and which fusion/reranking options were enabled versus disabled?
- **A:** It added the WRITING_SEARCH AI Search binding for the shuyang-website-rag corpus with remote: true, and the server-only call used hybrid retrieval with RRF, keyword and, reranking on, query rewrite off, and cache off.
- **sentinels:** `WRITING_SEARCH`, `shuyang-website-rag`, `RRF`
- **primary:** `llm-sessions-history/2026-06-05/0109-codex-ai-search-retrieval-bridge.md`
- **evidence:** llm-sessions-history/2026-06-05/0109-codex-ai-search-retrieval-bridge.md:32:- Added the `WRITING_SEARCH` AI Search binding for `shuyang-website-rag` with `remote: true`. ; :37:hybrid retrieval, RRF, keyword `and`, reranking on, query rewrite off, and cache off.

### web-openai-shirt-thought-racer-winner

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** When a second LLM provider was added in parallel to the GCP path for shirt thoughts, which OpenAI model was chosen as the default and what subtle rule decided which provider's result actually wins the race?
- **A:** The session chose gpt-4.1-mini as the default OpenAI model and made the race use the first successful parsed thought, not the first network response, so a fast error or empty response does not win, aborting the slower provider afterward.
- **sentinels:** `gpt-4.1-mini`, `first successful parsed thought, not the first network response`
- **primary:** `llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md`
- **evidence:** llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md:27:`gpt-4.1-mini` as the default OpenAI model ; :36:- Uses the first successful parsed thought, not the first network response, so ; :38:- Aborts the slower in-flight provider after a winner is selected.

### web-jj-workspace-vs-worktree-constraint

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** The research note on agent isolation rejected switching to native per-session Jujutsu workspaces. What concrete defect of that approach was verified on the machine, and which upstream tracking issue is cited as the reason colocation isn't yet possible?
- **A:** The note verified that a native jj workspace add working copy has .jj but no .git, so git status fails inside it; colocated-workspace support is still open upstream as jj#8052, so the recommendation keeps colocated git+jj working copies instead.
- **sentinels:** `jj workspace add`, `no `.git``, `jj#8052`
- **primary:** `docs/research/jj-agent-worktrees-2026-06.md`
- **evidence:** docs/research/jj-agent-worktrees-2026-06.md:13:- **Don't go pure `jj workspace add`.** Verified on this machine (jj 0.41): a `jj workspace add` working copy has `.jj` but **no `.git`**; `git status` inside it fails. Colocated-workspace support is still open upstream ([jj#8052](https://github.com/jj-vcs/jj/issues/8052))

### web-feature-flag-audience-rule-vocabulary

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** In the feature-flags documentation, what are the allowed audience-targeting values a flag can declare in its global config, and what user-key convention is shared with the avatar portrait system to keep raw auth IDs out of object keys?
- **A:** Each flag's audience rule is one of everyone, signed-in, signed-out, or none. The per-user override object key uses {userIdHash}, the first 16 hex chars of SHA-256(user.id), matching the avatar portrait key convention so raw auth IDs never appear in keys.
- **sentinels:** ``everyone`, `signed-in`, `signed-out`, or `none``, `flags/v1/users/{userIdHash}.json`, `first 16 hex chars of `SHA-256(user.id)``
- **primary:** `shuyang-website/src/lib/feature-flags.md`
- **evidence:** shuyang-website/src/lib/feature-flags.md:11:  audience rule (`everyone`, `signed-in`, `signed-out`, or `none`), and a default ; :13:- `flags/v1/users/{userIdHash}.json` — optional signed-in user overrides. ; :15:  `{userIdHash}` is the first 16 hex chars of `SHA-256(user.id)`

### web-mirror-runtime-refresh-extensions-readmeflag

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** In the GitHub mirror documentation, what staleness threshold triggers the Worker's lightweight read-through refresh, which file extensions count as Markdown for the full manual sync, and how do you keep an allowlisted repo metadata-only?
- **A:** The runtime serves the cached R2 index but does a lightweight read-through refresh when the index is missing or older than 6 h. The manual CLI sync treats .md, .markdown, .mdown, .mkd, .mkdn, and .mdx as Markdown, and setting "includeReadme": false in repos.json keeps a repo metadata-only with no README alias or Markdown bodies.
- **sentinels:** `older than 6 h`, ``.markdown`, `.mdown`, `.mkd`, `.mkdn`, `.mdx``, `"includeReadme": false`
- **primary:** `shuyang-website/src/lib/github-mirror.md`
- **evidence:** shuyang-website/src/lib/github-mirror.md:17:3. If the R2 index is missing or older than 6 h, `refreshFromGitHub()` does a ; :62:  Markdown file (`.md`, `.markdown`, `.mdown`, `.mkd`, `.mkdn`, `.mdx`) ; :71:Set `"includeReadme": false` in `repos.json` to keep an allowlisted repo

### web-mirror-allowlist-repos-and-token-source

- **slice:** design-doc · **difficulty:** easy · **source:** codex
- **Q:** According to the github-mirror tooling overview, which specific repositories are currently selected in the committed allowlist, and where does local setup read the read-only GitHub token from?
- **A:** The committed allowlist (repos.json) currently selects shuyangsun/website, shuyangsun/alpha-zero, shuyangsun/alpha-zero-api, and shuyangsun/alpha-zero-game. Local setup reads the token from the 1Password reference op://DevPersonal/shuyang-website/github-token-readonly.
- **sentinels:** `shuyangsun/alpha-zero-api`, `shuyangsun/alpha-zero-game`, `op://DevPersonal/shuyang-website/github-token-readonly`
- **primary:** `tools/github-mirror/OVERVIEW.md`
- **evidence:** tools/github-mirror/OVERVIEW.md:11:  `shuyangsun/alpha-zero-api`, and `shuyangsun/alpha-zero-game`; add only repos ; :10:  `shuyangsun/website`, `shuyangsun/alpha-zero`, ; :39:  `op://DevPersonal/shuyang-website/github-token-readonly`.

### web-consent-choice-span-and-region-stub

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** How does the consent system make aggregate tier counts possible without attaching any cookie-themed or identifying data, and what does the geo-detection helper currently return?
- **A:** After an analytics or essential choice, chooseTier() calls recordConsentChoice(), a server function that emits a minimal Langfuse consent.choice span carrying only a technical observability-profile tag and no input, output, user ID, or session ID; the none tier makes no Langfuse call. getRegion() intentionally returns unknown today because geo-specific defaults are deferred.
- **sentinels:** `consent.choice`, `recordConsentChoice()`, `getRegion()`
- **primary:** `shuyang-website/src/lib/consent.md`
- **evidence:** shuyang-website/src/lib/consent.md:35:Langfuse `consent.choice` span with only a technical observability profile tag ; :34:`recordConsentChoice()` in the background. That server function emits a minimal ; :40:`getRegion()` intentionally returns `unknown` today.

### web-aisearch-setup-chunk-overlap-stemmer

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the session that recommended manual AI Search instance settings before any code, what chunk size and overlap were endorsed as a baseline, and which keyword tokenizer/stemmer was recommended for the writing-oriented corpus?
- **A:** The session recommended Workers AI smart-default embeddings with 1024-token chunks and 10% overlap as a baseline, and endorsed the Porter stemming tokenizer for the initial writing question-answering case, noting trigram tokenization might be worth a re-index later if exact code identifiers performed poorly.
- **sentinels:** `1024-token chunks`, `Porter`, `trigram`
- **primary:** `llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md`
- **evidence:** llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md:41:Recommended Workers AI smart-default embeddings, 1024-token chunks, and 10% ; :58:Recommended Porter/stemming for the initial writing-oriented question-answering ; :59:case, with a note that trigram tokenization may be worth a re-index later

### web-heropoint-compositelock-maskfeather-bug

- **slice:** session-prompting · **difficulty:** hard · **source:** codex
- **Q:** In the pointing-pose art-pipeline session, what strategy was adopted so only the new arm region changed instead of redrawing the whole figure, and what specific bug zeroed out the edit mask and how was it fixed?
- **A:** The session adopted the composite-lock strategy (generate the pose, then re-paste reference pixels everywhere outside the edited region). The empty-mask bug was caused by the sharp-based feather zeroing the mask; it was fixed by replacing it with a pure-JS separable box blur (3 passes), after which only about 12% of the figure (the arm) differed and the alpha bounding box stayed byte-identical.
- **sentinels:** `composite-lock`, `separable box blur`, `alpha bbox byte-identical`
- **primary:** `llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md`
- **evidence:** llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md:16:Confirmed the right strategy is the plan's **composite-lock** ; :50:Replaced it with a pure-JS separable box blur (3 passes ≈ Gaussian). Result: only ~12% of the figure (the arm) differs from hero; alpha bbox byte-identical → no crossfade jump.

### web-sapiens-seg-model-and-pose-retrace-chain

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** In the Sapiens proof-of-concept docs, which TorchScript segmentation checkpoint is used, and when a pose image is regenerated, which derived-asset scripts must be re-run in order to avoid a doubled arm or clipped finger?
- **A:** The segmentation uses the facebook/sapiens-seg-1b-torchscript checkpoint (with facebook/sapiens-normal-1b-torchscript for normals). When a pose image like the pointing pose is regenerated, every derived asset must be re-traced by re-running seg.py, then arm_cutout.py for the cutout, then head_geometry.py for the head trace, otherwise a stale cutout shows a doubled arm and clips the finger.
- **sentinels:** `facebook/sapiens-seg-1b-torchscript`, `arm_cutout.py`, `head-traces.json`
- **primary:** `docs/research/sapiens-poc/OVERVIEW.md`
- **evidence:** docs/research/sapiens-poc/OVERVIEW.md:30:Models: `facebook/sapiens-seg-1b-torchscript`, `facebook/sapiens-normal-1b-torchscript`. ; :32:Re-run `seg.py` → `arm_cutout.py` (cutout) → `head_geometry.py` (head trace, then splice into `head-traces.json`)

### web-shirt-enter-submit-modifier-ime-guard

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** When the explicit submitted-response interaction was added, what rule governs which keystrokes trigger a submission versus a newline, and what mobile interaction was wired to submit?
- **A:** Plain Enter prevents the default newline and submits, while Enter combined with Shift, Alt, Meta, or Ctrl and any in-progress IME composition do not submit; on mobile/coarse-pointer devices, blur submits the trimmed value.
- **sentinels:** `Shift/Alt/Meta/Ctrl Enter and IME composition`, `Mobile/coarse-pointer blur submits`
- **primary:** `llm-sessions-history/2026-06-05/0111-codex-shirt-response-submit.md`
- **evidence:** llm-sessions-history/2026-06-05/0111-codex-shirt-response-submit.md:25:plain Enter prevents the default newline and calls `onSubmit`; Shift/Alt/Meta/Ctrl Enter and IME composition still avoid submission. Mobile/coarse-pointer blur submits the trimmed value.
