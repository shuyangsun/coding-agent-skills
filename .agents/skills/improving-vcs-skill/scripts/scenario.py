#!/usr/bin/env python3
"""Deterministic content engine for the improving-vcs-skill harness.

This module is the SINGLE SOURCE OF TRUTH for *what* changes each agent makes.
The bash scripts (new-sandbox.sh, check-quality.sh) own VCS orchestration only;
all file content, per-agent diffs, the difficulty ladder, and the
correctness oracle live here, so the seeded work and the expected result can
never drift apart.

Why a content engine at all: we want to test *only* the VCS aspect — can many
agents integrate each other's work and resolve conflicts cleanly — without the
variance of agents authoring code. So the harness PRE-MAKES each agent's change
deterministically (this module), commits it on the agent's branch/bookmark, and
the agent's sole job is to integrate it onto `main`. Because every change is
deterministic, the *correct* merged result is also deterministic, so `check`
can score resolution quality objectively (union present, tie-break value
correct, files still parse, nothing extra), not just "no conflict markers".

Difficulty ladder (realistic, escalating conflict pressure):
  easy   - one small union conflict (CHANGELOG) + a per-agent disjoint file.
  medium - CHANGELOG + JSON plugin array + handler list (all union) + a
           same-line version tie-break among a subset of agents.
  hard   - all of the above for EVERY agent, PLUS a large multi-line block that
           every agent inserts at the same marker in transform() — big,
           overlapping, multi-file conflicts with many parallel agents.

Subcommands:
  seed                --repo DIR --difficulty D
  apply               --dir DIR  --difficulty D --agent K --ticket T
  spec                --difficulty D --agents N --round R [--out FILE]
  check               --dir DIR  --spec FILE
  start-instructions  --round R [--agent K]

`apply` and `seed` produce files; `spec` emits a machine-readable plan;
`check` reads an integrated working tree and verifies it against the plan.
`start-instructions` prints the exact, fully-specified change a *start*-task
agent must author by hand (so the brief embeds it verbatim) — same content the
`easy` `apply`/`spec` path expects, so the SAME oracle scores the result. The
start task tests session-START isolation (does the agent carve out its own
worktree/workspace before doing new work), not conflict resolution, so the work
itself is a single trivial, mechanical edit with no coding judgment.
"""
from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import sys

# --- the fixture project ----------------------------------------------------
# A tiny but realistic service repo. Baseline is identical across difficulties;
# difficulty only changes WHICH regions each agent touches and HOW big the
# changes are. The hot regions are designed so the correct resolution is
# mechanical (union the additive parts; for the one same-line field, keep the
# higher semantic version) — no code judgment, pure VCS etiquette.

FEATURES = [
    ("streaming export", "streaming"),
    ("input validation", "validation"),
    ("registry refresh", "registry"),
    ("retry backoff", "retry"),
    ("audit logging", "audit"),
    ("rate limiting", "ratelimit"),
    ("cache warmup", "cache"),
    ("schema migration", "schema"),
]

CHANGELOG = """\
# Changelog

## Unreleased

- baseline scaffolding (VCS-0000)

## 1.4.0

- first cut
"""

CONFIG_YAML = """\
name: demo
version: 1.4.0
log_level: info
max_retries: 3
"""

HANDLERS_PY = """\
# Registry of handler names wired into the dispatcher.
HANDLERS = [
    "noop",
]
"""

PIPELINE_PY = """\
def transform(records):
    result = []
    for r in records:
        # >>> pipeline steps <<<
        result.append(r)
    return result
"""

REGISTRY_OBJ = {"plugins": [{"id": "core", "summary": "core plugin", "enabled": True}]}


def registry_json() -> str:
    return json.dumps(REGISTRY_OBJ, indent=2) + "\n"


def baseline_files() -> dict[str, str]:
    """Path -> content for the seeded baseline (committed as VCS-0000)."""
    return {
        "docs/CHANGELOG.md": CHANGELOG,
        "app/config.yaml": CONFIG_YAML,
        "app/handlers.py": HANDLERS_PY,
        "app/pipeline.py": PIPELINE_PY,
        "app/registry.json": registry_json(),
    }


# --- per-agent metadata (deterministic from k) ------------------------------
def agent_meta(k: int, round_: int) -> dict:
    feature, slug = FEATURES[(k - 1) % len(FEATURES)]
    return {
        "k": k,
        "feature": feature,
        "slug": slug,
        "ticket": f"VCS-{round_}-{k}",
        "version": f"1.5.{k}",
    }


def active_regions(difficulty: str) -> list[str]:
    if difficulty == "easy":
        return ["changelog", "notes"]
    if difficulty == "medium":
        return ["changelog", "registry", "handlers", "version"]
    if difficulty == "hard":
        return ["changelog", "registry", "handlers", "version", "pipeline"]
    raise SystemExit(f"scenario.py: unknown difficulty '{difficulty}'")


def in_version_group(difficulty: str, k: int) -> bool:
    """Which agents touch the same-line version field (creating a tie-break).

    medium: odd-k agents only (>=2 of them so a tie-break exists at agents>=3);
    hard:   every agent (maximal same-line contention)."""
    if difficulty == "medium":
        return k % 2 == 1
    if difficulty == "hard":
        return True
    return False


def agent_touches(difficulty: str, k: int) -> list[str]:
    regions = active_regions(difficulty)
    touches = []
    for r in regions:
        if r == "version" and not in_version_group(difficulty, k):
            continue
        touches.append(r)
    return touches


# --- contribution strings (deterministic) -----------------------------------
def changelog_line(m: dict) -> str:
    return f"- {m['feature']} ({m['ticket']})"


def plugin_obj(m: dict) -> dict:
    return {
        "id": f"{m['slug']}-{m['k']}",
        "summary": f"{m['feature']} ({m['ticket']})",
        "enabled": True,
    }


def handler_entry(m: dict) -> str:
    return f'    "{m["slug"]}_{m["k"]}",'


def pipeline_block(m: dict) -> list[str]:
    # Multi-line, self-contained, valid-Python block. In hard mode every agent
    # inserts one of these at the SAME marker, so the union is a large conflict.
    return [
        f"        # step {m['k']}: {m['feature']} ({m['ticket']})",
        "        r = dict(r)",
        f'        r["{m["slug"]}_{m["k"]}"] = True',
    ]


def notes_file(m: dict) -> tuple[str, str]:
    path = f"notes/agent-{m['k']}.md"
    body = f"# {m['feature']} ({m['ticket']})\n\nNotes for agent {m['k']}'s work.\n"
    return path, body


# --- apply one agent's deterministic edits to a working tree ----------------
def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def apply_changelog(repo: str, m: dict) -> None:
    path = os.path.join(repo, "docs/CHANGELOG.md")
    text = _read(path)
    anchor = "## Unreleased\n\n"
    idx = text.index(anchor) + len(anchor)
    text = text[:idx] + changelog_line(m) + "\n" + text[idx:]
    _write(path, text)


def apply_registry(repo: str, m: dict) -> None:
    path = os.path.join(repo, "app/registry.json")
    data = json.loads(_read(path))
    data["plugins"].append(plugin_obj(m))
    _write(path, json.dumps(data, indent=2) + "\n")


def apply_handlers(repo: str, m: dict) -> None:
    path = os.path.join(repo, "app/handlers.py")
    text = _read(path)
    anchor = '    "noop",\n'
    idx = text.index(anchor) + len(anchor)
    text = text[:idx] + handler_entry(m) + "\n" + text[idx:]
    _write(path, text)


def apply_version(repo: str, m: dict) -> None:
    path = os.path.join(repo, "app/config.yaml")
    text = _read(path)
    text = re.sub(r"(?m)^version:\s*.*$", f"version: {m['version']}", text)
    _write(path, text)


def apply_pipeline(repo: str, m: dict) -> None:
    path = os.path.join(repo, "app/pipeline.py")
    text = _read(path)
    anchor = "        # >>> pipeline steps <<<\n"
    idx = text.index(anchor) + len(anchor)
    block = "\n".join(pipeline_block(m)) + "\n"
    text = text[:idx] + block + text[idx:]
    _write(path, text)


def apply_notes(repo: str, m: dict) -> None:
    rel, body = notes_file(m)
    _write(os.path.join(repo, rel), body)


APPLIERS = {
    "changelog": apply_changelog,
    "registry": apply_registry,
    "handlers": apply_handlers,
    "version": apply_version,
    "pipeline": apply_pipeline,
    "notes": apply_notes,
}


def cmd_seed(args) -> int:
    for rel, content in baseline_files().items():
        _write(os.path.join(args.repo, rel), content)
    return 0


def cmd_apply(args) -> int:
    # ticket overrides the computed one so new-sandbox controls the round label.
    k = args.agent
    m = agent_meta(k, _round_from_ticket(args.ticket, k))
    m["ticket"] = args.ticket
    for region in agent_touches(args.difficulty, k):
        APPLIERS[region](args.dir, m)
    return 0


def cmd_start_instructions(args) -> int:
    """Print the exact change a start-task agent must make (for the brief).

    This is the `easy` contribution for one agent — a CHANGELOG line plus a
    per-agent notes file — written out as literal, copy-exact instructions so
    the agent does zero coding judgment. The matching `spec --difficulty easy
    --agents 1` oracle then scores the integrated result, so what the brief asks
    for and what `check` verifies can never drift.
    """
    k = args.agent
    m = agent_meta(k, args.round)
    m["ticket"] = f"VCS-{args.round}-{k}"
    notes_rel, notes_body = notes_file(m)
    print(
        "Make exactly this one change — copy it verbatim, change nothing else:\n"
        "\n"
        f"1. In `docs/CHANGELOG.md`, directly under the `## Unreleased` heading\n"
        f"   (as the FIRST item of that list, above the existing entries), insert\n"
        f"   this line:\n"
        f"\n"
        f"       {changelog_line(m)}\n"
        f"\n"
        f"2. Create a new file `{notes_rel}` with exactly this content:\n"
        f"\n"
        + "".join(f"       {ln}\n" for ln in notes_body.splitlines())
        + "\n"
        "Do not touch any other file, and do not alter any other line. That one\n"
        "two-part edit is the entire feature for this ticket."
    )
    return 0


def _round_from_ticket(ticket: str, k: int) -> int:
    # ticket looks like VCS-<round>-<k>; fall back to 0 if it doesn't parse.
    mobj = re.match(r"VCS-(\d+)-\d+$", ticket or "")
    return int(mobj.group(1)) if mobj else 0


# --- build the machine-readable plan (spec.json) ----------------------------
def cmd_spec(args) -> int:
    n, diff, rnd = args.agents, args.difficulty, args.round
    metas = [agent_meta(k, rnd) for k in range(1, n + 1)]
    sentinels = [m["ticket"] for m in metas]

    regions = []
    active = active_regions(diff)

    if "changelog" in active:
        regions.append(
            {
                "file": "docs/CHANGELOG.md",
                "kind": "lines-union",
                "must_contain": [changelog_line(m) for m in metas],
                "baseline_keep": ["- baseline scaffolding (VCS-0000)", "- first cut"],
            }
        )
    if "registry" in active:
        regions.append(
            {
                "file": "app/registry.json",
                "kind": "json-array-union",
                "array_path": "plugins",
                "id_key": "id",
                "must_contain_ids": [plugin_obj(m)["id"] for m in metas],
                "baseline_ids": ["core"],
            }
        )
    if "handlers" in active:
        regions.append(
            {
                "file": "app/handlers.py",
                "kind": "lines-union",
                "must_contain": [handler_entry(m).strip() for m in metas],
                "baseline_keep": ['"noop",'],
            }
        )
    if "version" in active:
        group = [m for m in metas if in_version_group(diff, m["k"])]
        expected = max((m["version"] for m in group), key=_version_key)
        regions.append(
            {
                "file": "app/config.yaml",
                "kind": "version-tiebreak",
                "key": "version",
                "candidates": {m["ticket"]: m["version"] for m in group},
                "expected": expected,
            }
        )
    if "pipeline" in active:
        regions.append(
            {
                "file": "app/pipeline.py",
                "kind": "lines-union",
                "must_contain": [pipeline_block(m)[0].strip() for m in metas],
                "baseline_keep": ["result.append(r)"],
            }
        )
    if "notes" in active:
        regions.append(
            {
                "file": "notes",
                "kind": "disjoint-files",
                "files": {notes_file(m)[0]: m["ticket"] for m in metas},
            }
        )

    # structural validity: any file that must still parse after resolution.
    structural = []
    if "registry" in active:
        structural.append({"file": "app/registry.json", "check": "json"})
    if "handlers" in active:
        structural.append({"file": "app/handlers.py", "check": "py"})
    if "pipeline" in active:
        structural.append({"file": "app/pipeline.py", "check": "py"})
    if "version" in active:
        structural.append({"file": "app/config.yaml", "check": "yaml"})

    # files no agent touched must come through integration byte-identical to
    # baseline — a clean "no extra work / no clobber" signal.
    touched = set()
    for k in range(1, n + 1):
        for region in agent_touches(diff, k):
            if region == "notes":
                touched.add(notes_file(metas[k - 1])[0])
            else:
                touched.add(_region_file(region))
    unchanged = sorted(set(baseline_files()) - touched)

    spec = {
        "round": rnd,
        "difficulty": diff,
        "agents": n,
        "sentinels": sentinels,
        "regions": regions,
        "structural": structural,
        "unchanged_files": unchanged,
    }
    out = json.dumps(spec, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out)
    return 0


def _region_file(region: str) -> str:
    return {
        "changelog": "docs/CHANGELOG.md",
        "registry": "app/registry.json",
        "handlers": "app/handlers.py",
        "version": "app/config.yaml",
        "pipeline": "app/pipeline.py",
    }[region]


def _version_key(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


# --- the correctness oracle (check) -----------------------------------------
class Checker:
    def __init__(self, root: str):
        self.root = root
        self.fails: list[str] = []
        self.oks: list[str] = []

    def _path(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def _exists(self, rel: str) -> bool:
        if not os.path.isfile(self._path(rel)):
            self.fails.append(f"{rel}: file missing from integrated result")
            return False
        return True

    def lines_union(self, region: dict) -> None:
        rel = region["file"]
        if not self._exists(rel):
            return
        text = _read(self._path(rel))
        bad = False
        for needle in region.get("must_contain", []):
            c = text.count(needle)
            if c == 0:
                self.fails.append(f"{rel}: lost contribution (absent): {needle!r}")
                bad = True
            elif c > 1:
                self.fails.append(f"{rel}: duplicated contribution ({c}x): {needle!r}")
                bad = True
        for needle in region.get("baseline_keep", []):
            if needle not in text:
                self.fails.append(f"{rel}: baseline content dropped: {needle!r}")
                bad = True
        if not bad:
            self.oks.append(f"{rel}: union intact ({len(region.get('must_contain', []))} contributions, no dups)")

    def json_array_union(self, region: dict) -> None:
        rel = region["file"]
        if not self._exists(rel):
            return
        try:
            data = json.loads(_read(self._path(rel)))
        except json.JSONDecodeError as exc:
            self.fails.append(f"{rel}: invalid JSON after resolution ({exc})")
            return
        arr = data
        for key in region["array_path"].split("."):
            arr = arr.get(key, []) if isinstance(arr, dict) else []
        ids = [o.get(region["id_key"]) for o in arr if isinstance(o, dict)]
        want = list(region["must_contain_ids"]) + list(region.get("baseline_ids", []))
        bad = False
        for wid in want:
            c = ids.count(wid)
            if c == 0:
                self.fails.append(f"{rel}: lost array element id={wid!r}")
                bad = True
            elif c > 1:
                self.fails.append(f"{rel}: duplicated array element id={wid!r} ({c}x)")
                bad = True
        if not bad:
            self.oks.append(f"{rel}: array union intact ({len(want)} elements)")

    def version_tiebreak(self, region: dict) -> None:
        rel = region["file"]
        if not self._exists(rel):
            return
        text = _read(self._path(rel))
        mobj = re.search(r"(?m)^%s:\s*(\S+)\s*$" % re.escape(region["key"]), text)
        if not mobj:
            self.fails.append(f"{rel}: '{region['key']}' line missing or malformed")
            return
        got = mobj.group(1)
        if got != region["expected"]:
            self.fails.append(
                f"{rel}: {region['key']}={got!r}, expected {region['expected']!r} "
                f"(tie-break: keep the higher version among {region['candidates']})"
            )
        else:
            self.oks.append(f"{rel}: tie-break correct ({region['key']}={got})")

    def disjoint_files(self, region: dict) -> None:
        ok = True
        for rel, sentinel in region["files"].items():
            if not self._exists(rel):
                ok = False
                continue
            if sentinel not in _read(self._path(rel)):
                self.fails.append(f"{rel}: present but sentinel {sentinel!r} missing")
                ok = False
        if ok:
            self.oks.append(f"disjoint files intact ({len(region['files'])})")

    def structural(self, item: dict) -> None:
        rel, kind = item["file"], item["check"]
        if not self._exists(rel):
            return
        path = self._path(rel)
        if kind == "json":
            try:
                json.loads(_read(path))
                self.oks.append(f"{rel}: valid JSON")
            except json.JSONDecodeError as exc:
                self.fails.append(f"{rel}: invalid JSON ({exc})")
        elif kind == "py":
            try:
                py_compile.compile(path, doraise=True)
                self.oks.append(f"{rel}: compiles")
            except py_compile.PyCompileError as exc:
                self.fails.append(f"{rel}: does not compile ({exc.msg.strip()})")
        elif kind == "yaml":
            ok = True
            for ln in _read(path).splitlines():
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                if not re.match(r"^[\w.-]+:\s*.*$", s) and not s.startswith("- "):
                    self.fails.append(f"{rel}: malformed YAML line: {ln!r}")
                    ok = False
            if ok:
                self.oks.append(f"{rel}: well-formed YAML")

    def unchanged(self, rel: str) -> None:
        base = baseline_files().get(rel)
        if base is None:
            return
        if not self._exists(rel):
            return
        if _read(self._path(rel)) != base:
            self.fails.append(f"{rel}: changed though no agent touched it (extra/edited work?)")
        else:
            self.oks.append(f"{rel}: unchanged from baseline")


def cmd_check(args) -> int:
    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    chk = Checker(args.dir)

    dispatch = {
        "lines-union": chk.lines_union,
        "json-array-union": chk.json_array_union,
        "version-tiebreak": chk.version_tiebreak,
        "disjoint-files": chk.disjoint_files,
    }
    for region in spec.get("regions", []):
        dispatch[region["kind"]](region)
    for item in spec.get("structural", []):
        chk.structural(item)
    for rel in spec.get("unchanged_files", []):
        chk.unchanged(rel)

    for ok in chk.oks:
        print(f"  ok: {ok}")
    for f in chk.fails:
        print(f"  FAIL: {f}")
    return 1 if chk.fails else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("seed")
    sp.add_argument("--repo", required=True)
    sp.add_argument("--difficulty", required=True)
    sp.set_defaults(func=cmd_seed)

    ap = sub.add_parser("apply")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--difficulty", required=True)
    ap.add_argument("--agent", type=int, required=True)
    ap.add_argument("--ticket", required=True)
    ap.set_defaults(func=cmd_apply)

    spc = sub.add_parser("spec")
    spc.add_argument("--difficulty", required=True)
    spc.add_argument("--agents", type=int, required=True)
    spc.add_argument("--round", type=int, required=True)
    spc.add_argument("--out")
    spc.set_defaults(func=cmd_spec)

    ck = sub.add_parser("check")
    ck.add_argument("--dir", required=True)
    ck.add_argument("--spec", required=True)
    ck.set_defaults(func=cmd_check)

    si = sub.add_parser("start-instructions")
    si.add_argument("--round", type=int, required=True)
    si.add_argument("--agent", type=int, default=1)
    si.set_defaults(func=cmd_start_instructions)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
