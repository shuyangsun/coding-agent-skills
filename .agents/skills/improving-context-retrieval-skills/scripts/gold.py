#!/usr/bin/env python3
"""gold.py — deterministic single source of truth for the docs+rag harness.

This is the `scenario.py` analog for the docs/rag harness: it emits the gold
labels AND runs the IR scorers, so the two cannot drift. Doc/retrieval quality
has no computable oracle, so this module replaces the oracle with deterministic
surrogates (plan docs/plans/0002 §2):

  1. Gold-set IR metrics  — graded BEIR qrels -> precision/recall/MRR/nDCG.
  2. Sentinel factuality  — the answer must contain a known sentinel string.
  3. Build-time validation — every sentinel still occurs in its pinned doc.

The fact table below is grounded in this repository's own, machine-checkable
facts (verified at build time). It is a *seed*: the plan calls for 50-100+ queries
via cross-link enumeration and anchored paraphrases (a power calc); growing it is
ordinary round work. Everything here is stdlib-only so Phase-0 needs no services
and no eval-time LLM.

Non-circularity firewall (plan §6):
  - Queries are paraphrases, never echoes: a query may not contain its own
    sentinel, and its token-trigram Jaccard with the primary doc must stay under
    a pinned threshold (LEXICAL_OVERLAP_MAX).
  - Fixed dev/held-out split by stable hash(query_id) — tune on dev, clear the
    bar on held-out, never regenerated per round.
  - Self-reference / meta docs (this harness's own plan + transcript) are excluded
    from the corpus so the gold set never points at a doc that merely quotes a
    fact as an example.

Content-type axis (domains): facts carry a `domain` — "nl" (natural-language docs
under docs/, including exported session transcripts), "code" (the
inception/ app), or "image" (image-backed project context: source/docs/session
transcripts plus curated summary records keyed to real image paths). Each domain
is validated and scored against its OWN corpus, so code vs natural-language vs
image-backed project retrieval can be compared with separate metrics.

CLI:
  gold.py build    [--corpus DIR] [--code-corpus DIR] [--image-corpus DIR] [--out DIR]
                                                   # emit per-domain, validate
  gold.py validate [--corpus DIR] [--code-corpus DIR] [--image-corpus DIR]
                                                   # validation + firewall only
  gold.py facts    [--split ...] [--domain nl|code|image|all]
                                                   # list the fact table
  gold.py score    --run FILE --domain nl|code|image [--corpus DIR] [--split ...] [--k 5,10,20]
                                                   # score a retrieval run vs qrels
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

GOLD_SET_VERSION = "docs-rag-gold-v3"

# Token-trigram Jaccard(query, primary doc) above this is rejected as too-echoic.
LEXICAL_OVERLAP_MAX = 0.30

# Stable dev/held-out partition: held-out iff hash(query_id) is odd.
HELD_OUT_FRACTION_NOTE = "hash(query_id) parity; even=dev, odd=held-out"

# Docs excluded from natural-language corpus snapshots: this harness's own plan +
# the coding session that produced it + the benchmark reports it writes (all
# quote the gold facts/sentinels as worked examples), and directory-overview
# index files.
# Globs are matched against the corpus-root relative POSIX path with fnmatch, so
# '*' spans '/'. The OVERVIEW.md globs enforce the firewall this comment has always
# claimed: index docs aggregate many facts' sentinels, so leaving them in-corpus
# would let a retriever score a hit by returning the directory listing instead of
# the actual answer (and would inflate sentinel-mode qrels). The benchmark-report
# globs are the same self-reference guard: a context-retrieval harness report names
# gold sentinels (e.g. "380s") to explain misses, so it must never enter the corpus
# it measures. Match both the historical report names (*docs-skill* / *rag-skill* /
# *docs-rag*) and the current per-skill names (*setting-up-rag* / *updating-docs* /
# *retrieving-context*); vcs (and other) benchmark reports stay legitimate corpus docs.
EXCLUDE_GLOBS = [
    # this harness's design plan + the sessions that produced it (historical + current names)
    "plans/0002-improving-docs-and-rag-skills.md",
    "plans/*improving-docs-and-rag*.md",
    "plans/*improving-context-retrieval*.md",
    "transcripts/*/*improving-docs-and-rag*.md",
    "transcripts/*/*improving-context-retrieval*.md",
    # benchmark reports that quote gold sentinels (historical + current per-skill names)
    "benchmarks/*docs-skill*.md",
    "benchmarks/*rag-skill*.md",
    "benchmarks/*docs-rag*.md",
    "benchmarks/*setting-up-rag*.md",
    "benchmarks/*updating-docs*.md",
    "benchmarks/*retrieving-context*.md",
    # Phase-1 RAG eval set: the gold questions/sentinels for the 207-query set live
    # here (overview + per-repo files + eval-set.json). Indexing them would let a
    # retriever "answer" a coding-agent-skills query by returning the file that
    # quotes its own sentinel (0003 plan §"Self-reference exclusion"). Globs span
    # '/', so the trailing pattern also covers the subdirectory's files.
    "plans/2026-06-08/0003-rag-eval-set-phase-1.md",
    "plans/2026-06-08/0003-rag-eval-set-phase-1*",
    # the consolidated Phase-2 plan restates benchmark decisions/sentinels and the
    # pre-work harness lives in its sibling subdir — exclude both (0008 plan §2).
    "plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md",
    "plans/2026-06-08/0008-consolidated-rag-optimization-phase-2*",
    "OVERVIEW.md",
    "*/OVERVIEW.md",
]

# The code corpus (content-type axis, domain="code"). Phase-0 indexes the repo's
# own `inception/` TanStack Start app — a realistic target codebase built for this
# harness — so retrieval over CODE can be measured separately from natural-language
# docs ("inception only for now"). These select which files load and which trees
# to skip (build output, dependencies, lockfiles).
CODE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".css", ".html", ".md")
COMMON_SKIP_DIRS = {".git", ".jj"}
CODE_SKIP_DIRS = {"node_modules", "dist", "build", ".output", ".vite", ".nitro",
                  ".git", ".jj", ".turbo", "coverage", ".cache"}
CODE_SKIP_FILES = {"bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
VCS_BOUNDARY_MARKERS = (".git", ".jj")
IMAGE_EXTS = (".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif")
IMAGE_TEXT_EXTS = (
    ".md", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".jsonc",
    ".css", ".html", ".txt", ".py", ".toml", ".yaml", ".yml",
)
IMAGE_SKIP_DIRS = {
    ".git", ".jj", "node_modules", "dist", "build", ".output", ".vite",
    ".nitro", ".turbo", "coverage", ".cache", "__pycache__",
    ".agents", ".antigravitycli", ".claude", ".codex", ".cursor", ".github",
    ".githooks", ".tanstack", ".vscode", ".wrangler", "experimental",
}
IMAGE_SKIP_FILES = CODE_SKIP_FILES | {"bun.lock", "AGENTS.md", "CLAUDE.md", ".mcp.json"}
IMAGE_EXCLUDE_GLOBS = [
    "docs/design/*",
    "docs/OVERVIEW.md",
    "docs/plan/OVERVIEW.md",
    "llm-sessions-history/OVERVIEW.md",
    "llm-sessions-history/*/OVERVIEW.md",
]


IMAGE_SUMMARIES: dict[str, str] = {
    "shuyang-website/public/hero.webp": """Image asset summary: shuyang-website/public/hero.webp

Visual evidence from the image file: a watercolor/ink illustrated seated man in a
white T-shirt and dark jeans, holding a teacup close to his face. The shirt area is
blank enough for runtime text overlays.

Project context: this is the full-screen illustrated landing hero after a visitor
has made a cookie choice. The interactive landing page builds the "type on my
t-shirt" flow, ambient thoughts, and submitted marginalia around this resting
tea-drinking pose.

Why it exists: it is the canonical resting figure pose for the personal website,
and downstream derived assets such as arm cutouts, shirt geometry, and head traces
are regenerated when this image changes.

Context sources: shuyang-website/OVERVIEW.md; shuyang-website/public/OVERVIEW.md;
shuyang-website/src/OVERVIEW.md; prompts/20260525-cookie-picker-gen.md.

Retrieval sentinel: HERO_RESTING_TEA_LANDING
""",
    "shuyang-website/public/hero_arm.webp": """Image asset summary: shuyang-website/public/hero_arm.webp

Visual evidence from the image file: a transparent cutout containing the
tea-holding forearm, wristwatch, hand, and cup from the resting hero pose.

Project context: the site layers this cutout above dynamic T-shirt text so typed
words appear to pass underneath the forearm while the base hero image remains
below the text. It is tied to the same offline Sapiens segmentation work that
produces shirt-geometry.json.

Why it exists: it preserves the visual illusion that the resting pose's cup arm is
in front of the shirt lettering before any arm-out animation state is shown.

Context sources: shuyang-website/public/OVERVIEW.md; shuyang-website/src/OVERVIEW.md;
llm-sessions-history/2026-05-30/0079-claude-hero-cutout-layering.md.

Retrieval sentinel: RESTING_ARM_TEXT_MASK
""",
    "shuyang-website/public/hero_arm_out.webp": """Image asset summary: shuyang-website/public/hero_arm_out.webp

Visual evidence from the image file: a full illustrated seated figure variant
where the cup hand is moved outward to the image-right side instead of covering
the shirt.

Project context: the PixiJS hero animation spike crossfades between hero.webp and
this arm-out pose, and the site uses the related reaction when shirt text reaches
the arm. The assets have different intrinsic framing, so the prototype
auto-registers alpha bounds and seated-base centroid before blending the pose.

Why it exists: it is the animated alternate pose for revealing more of the shirt
area while keeping the seated figure aligned with the resting hero.

Context sources: experimental/pixijs-hero-anim/OVERVIEW.md;
experimental/phaser-landing/OVERVIEW.md; shuyang-website/public/OVERVIEW.md.

Retrieval sentinel: HERO_ARM_OUT_CUP_LIFT
""",
    "shuyang-website/public/hero_point.webp": """Image asset summary: shuyang-website/public/hero_point.webp

Visual evidence from the image file: the same seated illustrated figure holding a
cup near the face while the other hand points across the T-shirt area.

Project context: this generated pose is used when the page needs the character to
direct attention to the shirt interaction; the documented idle nudge briefly
crossfades to it after a visitor ignores the shirt input. The art pipeline
regenerated it through the hero-point artifact-fix spec so old resting-arm pixels
would not be preserved as a ghost arm.

Why it exists: it gives the landing page a pointing-to-shirt pose while preserving
the same figure identity and layout as the resting hero.

Context sources: shuyang-website/public/OVERVIEW.md; tools/art-pipeline/OVERVIEW.md;
tools/art-pipeline/specs/OVERVIEW.md.

Retrieval sentinel: POINTING_SHIRT_PROMPT_POSE
""",
    "shuyang-website/public/hero_point_arm.webp": """Image asset summary: shuyang-website/public/hero_point_arm.webp

Visual evidence from the image file: a transparent cutout of the pointing pose's
cup-side arm and hand, sampled from the same 1122 x 1402 pointing-pose pixels.

Project context: the pointing pose needed its own cup-arm overlay. A stale
cutout from an older 1133 x 1388 pose caused doubled-arm and clipped-finger
artifacts, so the project re-traced this asset from the regenerated
hero_point.webp and layered it above shirt text.

Why it exists: it lets shirt text tuck under the cup arm in the pointing pose
without damaging the pointing finger or duplicating the arm.

Context sources: shuyang-website/public/OVERVIEW.md;
llm-sessions-history/2026-05-30/0081-claude-hero-point-arm-cutout.md;
llm-sessions-history/2026-06-01/0087-claude-hero-point-arm-cutout-fix.md.

Retrieval sentinel: POINTING_ARM_CUTOUT_1122
""",
    "shuyang-website/public/hero_cookie_selection.webp": """Image asset summary: shuyang-website/public/hero_cookie_selection.webp

Visual evidence from the image file: the illustrated seated figure faces forward
with open hands and wears a white shirt reading "Pick a cookie"; a teacup sits
near the lower right.

Project context: first-time visitors see this cookie-picker figure before the
main landing hero. It introduces the consent choice before the saved preference
routes visitors to the full interactive page.

Why it exists: it turns consent selection into the site's visual entry state,
matching the hero character while changing the shirt message and pose.

Context sources: shuyang-website/OVERVIEW.md; shuyang-website/public/OVERVIEW.md;
llm-sessions-history/2026-05-25/0043-claude-cookie-picker-shirt-print.md.

Retrieval sentinel: COOKIE_SELECTOR_PICK_A_COOKIE
""",
    "shuyang-website/public/cookie_plain.webp": """Image asset summary: shuyang-website/public/cookie_plain.webp

Visual evidence from the image file: a round, scalloped plain biscuit or cookie
with small holes and no chocolate pieces.

Project context: this is one of the cookie-picker option illustrations. The docs
describe it as the essential/basic option art, distinct from the chocolate-chip
full-experience cookie and the empty no-cookie plate.

Why it exists: it gives the "essential" consent tier a concrete visual choice in
the cookie picker.

Context sources: shuyang-website/public/OVERVIEW.md; shuyang-website/OVERVIEW.md;
llm-sessions-history/2026-05-27/0071-claude-privacy-route.md.

Retrieval sentinel: COOKIE_OPTION_ESSENTIAL_PLAIN
""",
    "shuyang-website/public/cookie_chocolate.webp": """Image asset summary: shuyang-website/public/cookie_chocolate.webp

Visual evidence from the image file: a thick chocolate-chip cookie with visible
dark chocolate rounds and chunks.

Project context: this is one of the cookie-picker option illustrations. The docs
describe it as the full-experience cookie option.

Why it exists: it gives the consent tier that allows the richer AI/analytics
experience a more indulgent cookie illustration.

Context sources: shuyang-website/public/OVERVIEW.md; shuyang-website/OVERVIEW.md;
llm-sessions-history/2026-05-27/0071-claude-privacy-route.md.

Retrieval sentinel: COOKIE_OPTION_ANALYTICS_CHOCOLATE
""",
    "shuyang-website/public/cookie_none.webp": """Image asset summary: shuyang-website/public/cookie_none.webp

Visual evidence from the image file: an empty white doily-like plate with a few
crumbs and a small smear, with no cookie remaining.

Project context: this is one of the cookie-picker option illustrations. The docs
describe it as the no-cookie / none-tier option art; current implementation notes
route AI calls directly without Langfuse or gateway telemetry for that tier.

Why it exists: it lets visitors choose the strictest consent tier with a visual
that communicates no cookie rather than a different flavor.

Context sources: shuyang-website/public/OVERVIEW.md; shuyang-website/OVERVIEW.md;
llm-sessions-history/2026-05-27/0071-claude-privacy-route.md.

Retrieval sentinel: COOKIE_OPTION_NO_AI_EMPTY_PLATE
""",
    "shuyang-website/public/link-preview.webp": """Image asset summary: shuyang-website/public/link-preview.webp

Visual evidence from the image file: a social-card portrait of the seated hero
holding tea, with "Ask me anything" written on the shirt.

Project context: the public asset overview identifies this as the Open Graph /
social sharing preview image for the site.

Why it exists: it gives shared links a branded preview card that matches the
interactive landing hero and invites questions.

Context sources: shuyang-website/public/OVERVIEW.md.

Retrieval sentinel: LINK_PREVIEW_ASK_ME_ANYTHING
""",
}


@dataclass(frozen=True)
class Fact:
    """One anchored, machine-checkable fact -> one gold query.

    sentinels:   answer strings that must appear in a relevant doc (factuality).
    primary:     corpus-root-relative paths hand-pinned as primary (grade 2).
                 Build-time validation asserts every primary carries at least one
                 sentinel and every sentinel occurs in at least one primary.
    supporting:  corpus-root-relative paths that should be retrieved as
                 corroborating context (grade 1). Image-domain facts use this
                 for actual image paths so project-context answers carry visual
                 provenance without making "describe this image" the task.
    qtype:       fact family (benchmark|issue|skill-behavior|cross-link|history|
                 code|session-transcript|image).
    difficulty:  easy|medium|hard (hard => multi-sentinel across doc types).
    domain:      content type, which corpus the fact is scored against:
                 "nl"   = natural-language docs (markdown under docs/, incl. the
                          exported session transcripts), or
                 "code" = the inception/ codebase (source + config files).
                 "image" = image-backed project context: source/docs/session
                          transcripts plus curated summaries keyed to real image
                          file paths so a consumer can choose to inspect images
                          as supporting evidence.
                 The harness scores each domain separately so natural-language,
                 code, and image retrieval can be compared (plan: content-type axis).
                 `primary` paths are relative to that domain's corpus root.
    answerable_closed_book: if True, the model may know the sentinel without the
                 corpus (parametric leakage); such queries are excluded from the
                 factuality headline (the closed-book control, plan §6).
    """

    id: str
    query: str
    sentinels: tuple[str, ...]
    primary: tuple[str, ...]
    qtype: str
    difficulty: str
    domain: str = "nl"
    supporting: tuple[str, ...] = ()
    answerable_closed_book: bool = False


# --- The seed fact table (verified against docs/ at build time) -------------
FACTS: list[Fact] = [
    Fact(
        id="bench-conflict-time",
        query="By how much did tuning the version-control skill speed up resolving "
        "a whole batch of merge conflicts?",
        sentinels=("380s", "85s"),
        primary=("benchmarks/2026-06-06/0000-vcs-skill-conflict-resolution.md",),
        qtype="benchmark",
        difficulty="medium",
    ),
    Fact(
        id="orphan-empty-head",
        query="What stray jj change was left behind after a workspace was cleaned "
        "up, and how was it removed?",
        sentinels=("urruyqxt",),
        primary=("issues/2026-06-07/0007-workspace-cleanup-left-unreferenced-empty-side-head.md",),
        qtype="issue",
        difficulty="hard",
    ),
    Fact(
        id="name-metric-transaction-hook",
        query="How is the workspace-naming convention scored durably even though "
        "branch names disappear when a branch is deleted?",
        sentinels=("reference-transaction",),
        primary=("transcripts/2026-06-06/0012-claude-vcs-skill-name-metric.md",),
        qtype="skill-behavior",
        difficulty="medium",
    ),
    Fact(
        id="composer-benchmark",
        query="Which coding model was benchmarked head-to-head on Jujutsu versus "
        "plain Git for the version-control skill?",
        sentinels=("Composer 2.5",),
        primary=("benchmarks/2026-06-07/0002-vcs-skill-composer-2.5-jj-vs-git.md",),
        qtype="benchmark",
        difficulty="medium",
    ),
    Fact(
        id="integrate-degenerate-merge",
        query="Why did landing finished work through the integrate helper sometimes "
        "create an empty merge that could not be pushed?",
        sentinels=("degenerate",),
        primary=("issues/2026-06-07/0003-jj-integrate-forms-degenerate-empty-merge-blocking-push.md",),
        qtype="issue",
        difficulty="medium",
    ),
    # --- Natural-language: exported session transcript (domain="nl") ----
    # Retrieval over an exported session transcript (long, dialog-shaped prose) —
    # a distinct content type from the issue/benchmark docs above.
    Fact(
        id="session-inception-toolchain",
        query="Which exported session transcript recorded setting up the demo web app so it "
        "type-checks with the experimental native-Go build of the TypeScript "
        "compiler instead of plain tsc?",
        sentinels=("native-preview",),
        primary=("transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        qtype="session-transcript",
        difficulty="medium",
        domain="nl",
    ),
    # --- Code: the inception/ TanStack Start app (domain="code") ---------------
    # "inception only for now": primaries are relative to the inception/ root, and
    # these are scored against the code corpus, never the docs corpus.
    Fact(
        id="code-router-preload",
        query="In the inception web app, how does the client-side router decide "
        "when to prefetch a route's code and data ahead of the user navigating?",
        sentinels=("defaultPreload",),
        primary=("src/router.tsx",),
        qtype="code",
        difficulty="medium",
        domain="code",
    ),
    Fact(
        id="code-react-compiler",
        query="How does the inception Vite build switch on React's automatic "
        "memoization — name the rolldown/babel plugin it loads and the preset it "
        "applies to it?",
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
        primary=("vite.config.ts",),
        qtype="code",
        difficulty="hard",
        domain="code",
    ),
    Fact(
        id="code-typecheck-tsgo",
        query="What package script type-checks the inception sources, and which "
        "non-tsc compiler binary does it invoke under the hood?",
        sentinels=("tsgo --noEmit",),
        primary=("package.json",),
        qtype="code",
        difficulty="medium",
        domain="code",
    ),
    # --- Image-backed project context (domain="image") -----------------------
    # These are development questions about the website project, not image
    # caption questions. Grade-2 primaries are code/docs/session transcripts that
    # answer the question; grade-1 supporting paths are the real images a human
    # answer should cite or inspect as visual evidence.
    Fact(
        id="image-arm-cutout-dom-layering",
        query="How does the website make shirt text pass under the hero's arm "
        "even though the figure itself is rendered with Phaser?",
        sentinels=("a single canvas can't sandwich", ".sprite-frame__cutout", "z-index 3"),
        primary=(
            "shuyang-website/src/components/phaser-figure-stage.tsx",
            "shuyang-website/src/styles.css",
            "shuyang-website/src/components/OVERVIEW.md",
            "llm-sessions-history/2026-05-30/0079-claude-hero-cutout-layering.md",
        ),
        supporting=(
            "shuyang-website/public/hero.webp",
            "shuyang-website/public/hero_arm.webp",
            "shuyang-website/public/hero_point.webp",
            "shuyang-website/public/hero_point_arm.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-pointing-cutout-regeneration",
        query="What went wrong after the pointing hero artwork changed, and "
        "which derived files need to stay synchronized with that pose?",
        sentinels=("1133×1388", "When a pose IMAGE is regenerated", "HERO_POINT_CUTOUT"),
        primary=(
            "llm-sessions-history/2026-06-01/0087-claude-hero-point-arm-cutout-fix.md",
            "docs/research/sapiens-poc/OVERVIEW.md",
            "shuyang-website/src/components/interactive-landing.tsx",
        ),
        supporting=(
            "shuyang-website/public/hero_point.webp",
            "shuyang-website/public/hero_point_arm.webp",
            "shuyang-website/public/hero.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-sapiens-arm-cutout-method",
        query="How is the blocking arm extracted from the illustrated hero, and "
        "why did the implementation avoid keeping only one connected blob?",
        sentinels=("drop_speckle", "largest_blob", "image-right collision arm", "edge_x"),
        primary=(
            "docs/research/sapiens-poc/arm_cutout.py",
            "docs/research/sapiens-poc/OVERVIEW.md",
            "llm-sessions-history/2026-05-24/0019-claude-arm-cutout-text-reveal.md",
        ),
        supporting=(
            "shuyang-website/public/hero.webp",
            "shuyang-website/public/hero_arm.webp",
            "shuyang-website/public/hero_point.webp",
            "shuyang-website/public/hero_point_arm.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-pointing-cup-arm-selection",
        query="For the pointing hero pose, which arm actually needs the text-mask "
        "cutout and what browser evidence corrected the first attempt?",
        sentinels=("My `image-left` asset cut the wrong arm", "--arm image-right", "pointing hand sits left of the print box"),
        primary=(
            "llm-sessions-history/2026-05-30/0081-claude-hero-point-arm-cutout.md",
            "docs/research/sapiens-poc/arm_cutout.py",
            "docs/research/sapiens-poc/OVERVIEW.md",
            "shuyang-website/src/components/phaser-figure-stage.tsx",
        ),
        supporting=(
            "shuyang-website/public/hero_point.webp",
            "shuyang-website/public/hero_point_arm.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-pointing-pose-registration",
        query="Why does the shirt text need a special horizontal adjustment "
        "during the pointing pose, and how is that offset measured?",
        sentinels=("registerPrintShift", "chestCenterX", "6.85–6.9%", "printShiftX"),
        primary=(
            "shuyang-website/src/lib/figure-align.ts",
            "shuyang-website/src/components/interactive-landing.tsx",
            "shuyang-website/src/components/shirt-text.tsx",
            "llm-sessions-history/2026-05-31/0082-claude-hero-point-text-align.md",
            "shuyang-website/src/components/OVERVIEW.md",
        ),
        supporting=(
            "shuyang-website/public/hero.webp",
            "shuyang-website/public/hero_point.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-hero-point-art-pipeline",
        query="Why did the project need a repeatable image-generation pipeline "
        "for the pointing hero pose, and how did the later prompt avoid the old "
        "arm artifact?",
        sentinels=("composite-lock", "lockedRegionFidelity", "hero-point-artifact-fix", "old-arm artifact"),
        primary=(
            "tools/art-pipeline/OVERVIEW.md",
            "tools/art-pipeline/specs/OVERVIEW.md",
            "tools/art-pipeline/specs/hero-point-artifact-fix.json",
            "docs/plan/image-generation-pipeline-2026-05.md",
            "llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md",
            "llm-sessions-history/2026-06-01/0088-codex-hero-point-artifact-fix.md",
        ),
        supporting=(
            "shuyang-website/public/hero.webp",
            "shuyang-website/public/hero_point.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-cookie-consent-assets",
        query="How do the cookie illustrations connect to the site's consent "
        "tiers and first-visit gate rather than acting as decorative assets?",
        sentinels=("COOKIE_CHOICES", "shirt-consent-v1", "window.location.replace(\"/cookies\")", "chooseTier"),
        primary=(
            "shuyang-website/src/components/cookie-picker.tsx",
            "shuyang-website/src/routes/cookies.tsx",
            "shuyang-website/src/routes/__root.tsx",
            "shuyang-website/src/lib/consent.md",
            "docs/plan/cookie-consent-2026-05.md",
        ),
        supporting=(
            "shuyang-website/public/hero_cookie_selection.webp",
            "shuyang-website/public/cookie_plain.webp",
            "shuyang-website/public/cookie_chocolate.webp",
            "shuyang-website/public/cookie_none.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-privacy-cookie-selection",
        query="How does the privacy page reuse the cookie art to explain the "
        "choices and mark the currently selected tier?",
        sentinels=("COOKIE_CARDS", "CookieRing", "privacy-card-ring-draw", "you picked this"),
        primary=(
            "shuyang-website/src/routes/privacy.tsx",
            "shuyang-website/src/styles.css",
            "shuyang-website/src/lib/consent.md",
            "shuyang-website/src/routes/OVERVIEW.md",
            "llm-sessions-history/2026-05-30/0080-claude-privacy-selected-cookie-ring.md",
        ),
        supporting=(
            "shuyang-website/public/cookie_plain.webp",
            "shuyang-website/public/cookie_chocolate.webp",
            "shuyang-website/public/cookie_none.webp",
        ),
        qtype="image-project-context",
        difficulty="hard",
        domain="image",
    ),
    Fact(
        id="image-social-preview-wiring",
        query="Where is the website's social sharing card wired into the app, "
        "and what project history explains the asset's purpose?",
        sentinels=("og:image", "twitter:image", "link-preview.webp", "social link preview"),
        primary=(
            "shuyang-website/src/routes/__root.tsx",
            "shuyang-website/public/OVERVIEW.md",
            "llm-sessions-history/2026-05-24/0018-gemini-tanstack-start-link-preview.md",
        ),
        supporting=("shuyang-website/public/link-preview.webp",),
        qtype="image-project-context",
        difficulty="medium",
        domain="image",
    ),
]


# --- Corpus loading ----------------------------------------------------------
def find_corpus_root(explicit: str | None) -> Path:
    """Locate the corpus root (a directory of .md docs). Defaults to repo docs/."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"gold.py: corpus dir not found: {p}")
        return p
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "docs"
        if (cand / "benchmarks").is_dir() or (cand / "issues").is_dir():
            return cand.resolve()
    sys.exit("gold.py: could not auto-locate docs/ corpus; pass --corpus DIR")


def find_code_corpus_root(explicit: str | None) -> Path | None:
    """Locate the code corpus root (the inception/ app). Returns None if absent,
    so a checkout without inception/ can still run the natural-language domain."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"gold.py: code corpus dir not found: {p}")
        return p
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "inception"
        if (cand / "package.json").is_file():
            return cand.resolve()
    return None


def find_image_corpus_root(explicit: str | None) -> Path | None:
    """Locate the optional image corpus root.

    Image fixtures intentionally require an explicit root (or
    CONTEXT_RETRIEVAL_IMAGE_CORPUS) instead of assuming a host-project layout. The
    currently bundled image facts target the `website` project, so pass that
    project's root (or a snapshot created by mk-corpus.py).
    """
    raw = explicit or os.environ.get("CONTEXT_RETRIEVAL_IMAGE_CORPUS")
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        sys.exit(f"gold.py: image corpus dir not found: {p}")
    # The bundled image-backed facts target the website monorepo root. If a user
    # passes the nested app (`.../website/shuyang-website`), widen to the parent
    # when it contains the project history/tools needed for deep answers.
    if (
        p.name == "shuyang-website"
        and (p / "public" / "hero.webp").is_file()
        and (p.parent / "llm-sessions-history").is_dir()
    ):
        return p.parent
    return p


def is_excluded(relpath: str) -> bool:
    return any(fnmatch.fnmatch(relpath, g) for g in EXCLUDE_GLOBS)


def is_vcs_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in VCS_BOUNDARY_MARKERS)


def iter_corpus_files(corpus_root: Path, kind: str):
    """Yield corpus files without crossing nested Git/Jujutsu workspace roots.

    A directly selected corpus may itself be a Git worktree or Jujutsu workspace.
    Only VCS roots below that selected root are skipped, preventing nested
    workspaces/worktrees from being treated as newly added project files.
    """
    if kind == "md":
        skip_dirs = COMMON_SKIP_DIRS

        def wanted(name: str) -> bool:
            return name.endswith(".md")
    elif kind == "code":
        skip_dirs = CODE_SKIP_DIRS

        def wanted(name: str) -> bool:
            return name.endswith(CODE_EXTS)
    elif kind == "image":
        skip_dirs = IMAGE_SKIP_DIRS

        def wanted(name: str) -> bool:
            low = name.lower()
            return low.endswith(IMAGE_EXTS) or low.endswith(IMAGE_TEXT_EXTS)
    else:
        raise ValueError(f"unknown corpus kind: {kind!r}")

    for dirpath, dirnames, filenames in os.walk(corpus_root):
        current = Path(dirpath)
        if current != corpus_root and is_vcs_root(current):
            dirnames[:] = []
            continue

        kept_dirs = []
        for dirname in sorted(dirnames):
            child = current / dirname
            if dirname in skip_dirs or is_vcs_root(child):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            if wanted(filename):
                yield current / filename


def load_corpus(corpus_root: Path, kind: str = "md") -> dict[str, str]:
    """Map corpus-root-relative POSIX path -> document text.

    kind="md"    : every *.md under the root, minus EXCLUDE_GLOBS (the docs/NL
                   domain: issues, benchmarks, transcripts, …).
    kind="code"  : every CODE_EXTS file under the root, skipping dependency/build
                   dirs and lockfiles (the inception/ code domain).
    kind="image" : image-backed project context. Text/code/config files are
                   indexed verbatim, while known image assets are represented by
                   curated summaries whose doc id remains the real image path.
                   Phase-0 indexes text; READ consumers can decide whether to
                   inspect the image file named by a supporting hit.
    """
    docs: dict[str, str] = {}
    for path in iter_corpus_files(corpus_root, kind):
        rel = path.relative_to(corpus_root).as_posix()
        if kind == "code":
            if path.name in CODE_SKIP_FILES:
                continue
        elif kind == "image":
            if rel.startswith("."):
                continue
            if path.name in IMAGE_SKIP_FILES:
                continue
            if any(fnmatch.fnmatch(rel, g) for g in IMAGE_EXCLUDE_GLOBS):
                continue
            if path.suffix.lower() in IMAGE_EXTS:
                summary = IMAGE_SUMMARIES.get(rel)
                if summary is None:
                    continue
                docs[rel] = summary
                continue
        elif is_excluded(rel):
            continue
        try:
            docs[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - defensive
            print(f"gold.py: warning: cannot read {rel}: {exc}", file=sys.stderr)
    return docs


# --- Text utilities for the firewall ----------------------------------------
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def trigrams(toks: list[str]) -> set[tuple[str, str, str]]:
    return {tuple(toks[i : i + 3]) for i in range(len(toks) - 2)} if len(toks) >= 3 else set()


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


# --- qrels construction ------------------------------------------------------
def build_qrels(
    facts: list[Fact], docs: dict[str, str], mode: str = "pinned"
) -> dict[str, dict[str, int]]:
    """Graded relevance labels per query, in one of two modes:

    - ``pinned`` (GOLD/D plane): hand-pinned primary docs are grade 2; supporting
      docs are grade 1; any other corpus doc that contains a sentinel is grade 1
      (corroborating). Used where structured paths are stable. Plan §6: never
      singletons when the corpus genuinely repeats a fact.
    - ``sentinel`` (per-corpus N/D plane): purely sentinel-derived, so it works
      for any corpus structure (naive dumps with opaque filenames included). A
      doc containing ALL of a fact's sentinels is grade 2; a doc containing some
      (but not all) is grade 1. Plan §3: labels are derived from the sentinels
      actually present in each corpus's files, never from GOLD's paths.
    """
    qrels: dict[str, dict[str, int]] = {}
    for fact in facts:
        rel: dict[str, int] = {}
        if mode == "pinned":
            for p in fact.primary:
                rel[p] = 2
            for p in fact.supporting:
                rel[p] = max(rel.get(p, 0), 1)
            for doc_id, text in docs.items():
                if doc_id in rel:
                    continue
                if any(s in text for s in fact.sentinels):
                    rel[doc_id] = 1
        elif mode == "sentinel":
            n = len(fact.sentinels)
            for doc_id, text in docs.items():
                present = sum(1 for s in fact.sentinels if s in text)
                if present == 0:
                    continue
                rel[doc_id] = 2 if present == n else 1
        else:
            raise ValueError(f"unknown qrels mode: {mode}")
        qrels[fact.id] = rel
    return qrels


def split_of(query_id: str) -> str:
    h = int(hashlib.sha256(query_id.encode()).hexdigest(), 16)
    return "held-out" if h % 2 else "dev"


# --- Validation + firewall ---------------------------------------------------
def validate(facts: list[Fact], corpora: dict[str, dict[str, str]]) -> list[str]:
    """Return a list of error strings (empty => valid).

    `corpora` maps domain ("nl"|"code"|"image") -> that domain's {path: text}.
    Each fact is validated against the corpus for its own domain, so a code
    fact's primary is checked in inception/, an nl fact's in docs/, and an image
    fact's primaries/supporting paths in the image-backed project corpus."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for fact in facts:
        if fact.id in seen_ids:
            errors.append(f"[{fact.id}] duplicate fact id")
        seen_ids.add(fact.id)
        if fact.difficulty not in ("easy", "medium", "hard"):
            errors.append(f"[{fact.id}] bad difficulty {fact.difficulty!r}")
        docs = corpora.get(fact.domain)
        if docs is None:
            errors.append(f"[{fact.id}] no corpus loaded for domain {fact.domain!r} "
                          f"(have: {sorted(corpora)})")
            continue
        # Primary docs exist and carry sentinels. For multi-primary facts, a
        # question may need both code and a session transcript; requiring every
        # sentinel in every primary would force unnatural duplicate anchors.
        sentinel_hits = {s: 0 for s in fact.sentinels}
        for p in fact.primary:
            if p not in docs:
                errors.append(f"[{fact.id}] primary doc missing from corpus: {p}")
                continue
            present_in_primary = 0
            for s in fact.sentinels:
                if s in docs[p]:
                    sentinel_hits[s] += 1
                    present_in_primary += 1
            if present_in_primary == 0:
                errors.append(f"[{fact.id}] no sentinel occurs in primary {p}")
        for s, count in sentinel_hits.items():
            if count == 0:
                errors.append(f"[{fact.id}] sentinel {s!r} not found in any primary")
        # supporting docs exist; they need not contain the sentinel because they
        # may be image paths whose visual evidence backs the code/NL primary.
        for p in fact.supporting:
            if p not in docs:
                errors.append(f"[{fact.id}] supporting doc missing from corpus: {p}")
        # firewall 1a: query must not echo a sentinel verbatim
        q_low = fact.query.lower()
        for s in fact.sentinels:
            if s.lower() in q_low:
                errors.append(f"[{fact.id}] query echoes sentinel {s!r} (not a paraphrase)")
        # firewall 1b: token-trigram overlap with primary doc must stay low
        q_tri = trigrams(tokens(fact.query))
        for p in fact.primary:
            if p in docs:
                j = jaccard(q_tri, trigrams(tokens(docs[p])))
                if j > LEXICAL_OVERLAP_MAX:
                    errors.append(
                        f"[{fact.id}] query-vs-{p} trigram Jaccard {j:.3f} > "
                        f"{LEXICAL_OVERLAP_MAX} (too echoic)"
                    )
    return errors


# --- IR metrics (the shared scorer; check-retrieval.py imports these) --------
def _dcg(grades: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def score_query(ranked: list[str], rel: dict[str, int], ks: list[int]) -> dict[str, float]:
    """Graded IR metrics for one query. `ranked` is the ordered doc-id list."""
    relevant = {d for d, g in rel.items() if g >= 1}
    out: dict[str, float] = {}
    for k in ks:
        topk = ranked[:k]
        hits = sum(1 for d in topk if d in relevant)
        out[f"recall@{k}"] = hits / len(relevant) if relevant else 0.0
        out[f"precision@{k}"] = hits / k if k else 0.0
        ideal = sorted(rel.values(), reverse=True)[:k]
        dcg = _dcg([rel.get(d, 0) for d in topk])
        idcg = _dcg(ideal)
        out[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    mrr = 0.0
    for i, d in enumerate(ranked):
        if d in relevant:
            mrr = 1.0 / (i + 1)
            break
    out["mrr"] = mrr
    return out


def aggregate(per_query: dict[str, dict[str, float]]) -> dict[str, float]:
    if not per_query:
        return {}
    keys = next(iter(per_query.values())).keys()
    return {k: sum(q[k] for q in per_query.values()) / len(per_query) for k in keys}


# --- Output ------------------------------------------------------------------
def emit(out_dir: Path, facts: list[Fact], docs: dict[str, str], qrels) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # BEIR-style qrels TSV: query-id <tab> corpus-id <tab> score
    with (out_dir / "qrels.tsv").open("w", encoding="utf-8") as fh:
        fh.write("query-id\tcorpus-id\tscore\n")
        for qid in sorted(qrels):
            for doc_id in sorted(qrels[qid]):
                fh.write(f"{qid}\t{doc_id}\t{qrels[qid][doc_id]}\n")
    # query records
    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as fh:
        for fact in facts:
            fh.write(
                json.dumps(
                    {
                        "query_id": fact.id,
                        "query": fact.query,
                        "sentinels": list(fact.sentinels),
                        "gold_doc_paths": list(fact.primary),
                        "supporting_doc_paths": list(fact.supporting),
                        "qrels": qrels[fact.id],
                        "difficulty": fact.difficulty,
                        "qtype": fact.qtype,
                        "domain": fact.domain,
                        "split": split_of(fact.id),
                        "answerable_closed_book": fact.answerable_closed_book,
                        "gold_set_version": GOLD_SET_VERSION,
                    }
                )
                + "\n"
            )
    # corpus manifest (doc-id -> length), so docs-eval indexes exactly this set
    with (out_dir / "corpus.jsonl").open("w", encoding="utf-8") as fh:
        for doc_id in sorted(docs):
            fh.write(json.dumps({"doc_id": doc_id, "chars": len(docs[doc_id])}) + "\n")
    summary = {
        "gold_set_version": GOLD_SET_VERSION,
        "n_queries": len(facts),
        "n_docs": len(docs),
        "split": {
            "dev": sum(1 for f in facts if split_of(f.id) == "dev"),
            "held-out": sum(1 for f in facts if split_of(f.id) == "held-out"),
        },
        "by_difficulty": {
            d: sum(1 for f in facts if f.difficulty == d) for d in ("easy", "medium", "hard")
        },
        "multi_relevant_queries": sum(1 for q in qrels.values() if len(q) > 1),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"gold.py: wrote qrels/records/corpus/summary to {out_dir}")
    print(json.dumps(summary, indent=2))


# --- Run scoring -------------------------------------------------------------
def load_run(run_file: Path) -> dict[str, list[str]]:
    """A run file is JSONL of {query_id, ranked:[doc_id,...]} or a single JSON
    object {query_id: [doc_id,...]}."""
    text = run_file.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text[0] == "{" and "\n" not in text.strip().splitlines()[0][:1] and text.count("\n") == 0:
        return {k: list(v) for k, v in json.loads(text).items()}
    runs: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        runs[obj["query_id"]] = list(obj["ranked"])
    return runs


def load_corpora(args) -> tuple[dict[str, dict[str, str]], Path]:
    """Load every domain corpus the fact table needs. The nl (docs) corpus is
    always loaded; optional code/image corpora are loaded when their roots are
    found. A checkout without inception/ or an image corpus degrades to nl-only
    or nl+code (a warning is printed and absent-domain facts are skipped, see
    active_facts).
    Returns (corpora_by_domain, nl_root)."""
    nl_root = find_corpus_root(args.corpus)
    corpora: dict[str, dict[str, str]] = {"nl": load_corpus(nl_root, kind="md")}
    if any(f.domain == "code" for f in FACTS):
        code_root = find_code_corpus_root(getattr(args, "code_corpus", None))
        if code_root is not None:
            corpora["code"] = load_corpus(code_root, kind="code")
        else:
            print("gold.py: warning: inception/ code corpus not found; skipping the "
                  "code domain (running natural-language facts only).", file=sys.stderr)
    if any(f.domain == "image" for f in FACTS):
        image_root = find_image_corpus_root(getattr(args, "image_corpus", None))
        if image_root is not None:
            corpora["image"] = load_corpus(image_root, kind="image")
        else:
            print("gold.py: warning: image corpus not found; skipping the image "
                  "domain (pass --image-corpus, or set CONTEXT_RETRIEVAL_IMAGE_CORPUS).",
                  file=sys.stderr)
    return corpora, nl_root


def active_facts(corpora: dict[str, dict[str, str]]) -> list[Fact]:
    """Facts whose domain corpus is loaded. Facts in an absent domain are skipped
    (their corpus could not be located), keeping validate/build nl-only-safe."""
    return [f for f in FACTS if f.domain in corpora]


def cmd_score(args) -> int:
    kind = {"nl": "md", "code": "code", "image": "image"}[args.domain]
    if kind == "code":
        root = find_code_corpus_root(args.corpus)
        if root is None:
            sys.exit("gold.py: code corpus (inception/) not found; pass --corpus DIR")
    elif kind == "image":
        root = find_image_corpus_root(args.corpus)
        if root is None:
            sys.exit("gold.py: image corpus not found; pass --corpus DIR")
    else:
        root = find_corpus_root(args.corpus)
    docs = load_corpus(root, kind=kind)
    facts = [f for f in FACTS if args.split in ("all", split_of(f.id)) and f.domain == args.domain]
    qrels = build_qrels(facts, docs)
    ks = [int(x) for x in args.k.split(",")]
    runs = load_run(Path(args.run))
    per_query: dict[str, dict[str, float]] = {}
    missing = []
    for fact in facts:
        if fact.id not in runs:
            missing.append(fact.id)
            continue
        per_query[fact.id] = score_query(runs[fact.id], qrels[fact.id], ks)
    agg = aggregate(per_query)
    for key in sorted(agg):
        print(f"{key}={agg[key]:.4f}")
    print(f"domain={args.domain}")
    print(f"n_scored={len(per_query)}")
    print(f"n_missing={len(missing)}")
    print(f"split={args.split}")
    print(f"gold_set_version={GOLD_SET_VERSION}")
    return 0


def cmd_build(args) -> int:
    corpora, nl_root = load_corpora(args)
    facts = active_facts(corpora)
    errors = validate(facts, corpora)
    if errors:
        print("gold.py: VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    out_dir = Path(args.out).expanduser().resolve() if args.out else nl_root.parent / "gold-set"
    for domain in sorted(corpora):
        dfacts = [f for f in facts if f.domain == domain]
        qrels = build_qrels(dfacts, corpora[domain])
        emit(out_dir / domain, dfacts, corpora[domain], qrels)
    print(f"gold.py: built {len(corpora)} domain(s) under {out_dir}: {sorted(corpora)}")
    return 0


def cmd_validate(args) -> int:
    corpora, _ = load_corpora(args)
    facts = active_facts(corpora)
    errors = validate(facts, corpora)
    if errors:
        print("gold.py: VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    for domain in sorted(corpora):
        dfacts = [f for f in facts if f.domain == domain]
        qrels = build_qrels(dfacts, corpora[domain])
        multi = sum(1 for q in qrels.values() if len(q) > 1)
        print(f"  {domain:<5} {len(dfacts):>2} facts  {len(corpora[domain]):>3} docs  "
              f"{multi} multi-relevant")
    print(f"gold.py: OK — {len(facts)} facts across {len(corpora)} domain(s)")
    return 0


def cmd_facts(args) -> int:
    for fact in FACTS:
        if args.split not in ("all", split_of(fact.id)):
            continue
        if args.domain not in ("all", fact.domain):
            continue
        print(f"{fact.id}\t{fact.domain}\t{split_of(fact.id)}\t{fact.difficulty}\t"
              f"{fact.qtype}\t{fact.query}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="emit qrels/records/corpus and validate")
    pb.add_argument("--corpus", help="docs/ (nl) corpus root")
    pb.add_argument("--code-corpus", help="inception/ (code) corpus root")
    pb.add_argument("--image-corpus", help="image corpus root, e.g. a website project root")
    pb.add_argument("--out")
    pb.set_defaults(func=cmd_build)

    pv = sub.add_parser("validate", help="validation + firewall only")
    pv.add_argument("--corpus", help="docs/ (nl) corpus root")
    pv.add_argument("--code-corpus", help="inception/ (code) corpus root")
    pv.add_argument("--image-corpus", help="image corpus root, e.g. a website project root")
    pv.set_defaults(func=cmd_validate)

    pf = sub.add_parser("facts", help="list the fact table")
    pf.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    pf.add_argument("--domain", choices=["nl", "code", "image", "all"], default="all")
    pf.set_defaults(func=cmd_facts)

    ps = sub.add_parser("score", help="score a retrieval run vs qrels")
    ps.add_argument("--run", required=True)
    ps.add_argument("--corpus", help="corpus root for the chosen --domain")
    ps.add_argument("--domain", choices=["nl", "code", "image"], default="nl")
    ps.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    ps.add_argument("--k", default="5,10,20")
    ps.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
