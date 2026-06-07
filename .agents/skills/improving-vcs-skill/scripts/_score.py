#!/usr/bin/env python3
"""Process a vcs-eval workflow result: score each round objectively, record one
metrics row per agent (round-level quality verdict, per the harness design),
then print the scoreboard.

Usage: _score.py <result.json> <harness-base> [<transcript-dir>]

<transcript-dir> is the workflow's transcript directory (printed when the runner
launches). If given, exact per-agent OUTPUT tokens are read from each
`agent-*.jsonl` there and mapped to (round, agent-k) by the ws-agent path baked
into that agent's prompt — concurrency-independent and far more reliable than a
budget.spent() delta. Omit it to record tokens=0."""
import json, subprocess, sys, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
result_path, base = sys.argv[1], sys.argv[2]
transcript_dir = sys.argv[3] if len(sys.argv) > 3 else None
rounds = json.load(open(result_path))


def build_token_map(tdir):
    """(round, k) -> summed output_tokens, read from each agent's transcript."""
    tmap = {}
    if not tdir or not os.path.isdir(tdir):
        return tmap
    for f in glob.glob(os.path.join(tdir, "agent-*.jsonl")):
        out_toks, prompt = 0, ""
        try:
            for line in open(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                msg = o.get("message", {}) if isinstance(o, dict) else {}
                u = msg.get("usage") if isinstance(msg, dict) else None
                if isinstance(u, dict):
                    out_toks += u.get("output_tokens", 0) or 0
                if not prompt and isinstance(msg, dict) and msg.get("role") == "user":
                    c = msg.get("content")
                    if isinstance(c, str):
                        prompt = c
                    elif isinstance(c, list):
                        prompt = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
        except OSError:
            continue
        m = re.search(r"round-(\d+)/ws-agent-(\d+)", prompt)
        if m:
            tmap[(int(m.group(1)), int(m.group(2)))] = out_toks
    return tmap


token_map = build_token_map(transcript_dir)

def sh(*a):
    p = subprocess.run(a, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

env_for = {"git": "cloud-git", "jj": "local-cli"}

for rd in rounds:
    if rd is None:
        print("!! a round returned null (workflow error)"); continue
    rnum, mode, diff = rd["round"], rd["mode"], rd["difficulty"]
    rdir = f"{base}/round-{rnum}"
    code, out, err = sh("bash", f"{HERE}/check-quality.sh", rdir)
    quality = "pass" if code == 0 else "fail"
    # hygiene is reported separately from correctness: parse which agent-K refs
    # were left behind (STALE_LIST) so we can attribute the stale-ref metric per
    # agent (the scoreboard then sums it per round and per tier).
    stale_set, stale_total = set(), 0
    orphan_ws_set, orphan_dir_set = set(), set()
    orphan_ws_total = orphan_dir_total = 0
    default_ok = "-"
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("STALE_LIST="):
            stale_set = set(s[len("STALE_LIST="):].split())
        elif s.startswith("STALE_REFS="):
            try:
                stale_total = int(s[len("STALE_REFS="):])
            except ValueError:
                stale_total = 0
        elif s.startswith("ORPHAN_WS_LIST="):
            orphan_ws_set = set(s[len("ORPHAN_WS_LIST="):].split())
        elif s.startswith("ORPHAN_DIR_LIST="):
            orphan_dir_set = set(s[len("ORPHAN_DIR_LIST="):].split())
        elif s.startswith("ORPHAN_WS="):
            try:
                orphan_ws_total = int(s[len("ORPHAN_WS="):])
            except ValueError:
                orphan_ws_total = 0
        elif s.startswith("ORPHAN_DIRS="):
            try:
                orphan_dir_total = int(s[len("ORPHAN_DIRS="):])
            except ValueError:
                orphan_dir_total = 0
        elif s.startswith("DEFAULT_OK="):
            v = s[len("DEFAULT_OK="):].strip()
            default_ok = v if v in ("pass", "fail") else "-"
    # session-start isolation (start rounds only). check-isolation.sh prints
    # ISOLATED=pass/fail for a `--task start` round, or ISOLATED=n/a (exit 2) for
    # an integration round — in which case the metric stays "-" (not measured).
    _ic, iout, _ie = sh("bash", f"{HERE}/check-isolation.sh", rdir)
    isolate = "-"
    name_ok = "-"
    for line in iout.splitlines():
        s = line.strip()
        if s.startswith("ISOLATED="):
            v = s[len("ISOLATED="):].strip()
            isolate = v if v in ("pass", "fail") else "-"
        elif s.startswith("NAME_OK="):
            v = s[len("NAME_OK="):].strip()
            name_ok = v if v in ("pass", "fail", "n/a") else "-"
    iso_note = f", isolated={isolate}" if isolate != "-" else ""
    if name_ok in ("pass", "fail"):
        iso_note += f", name={name_ok}"
    jj_note = ""
    if default_ok != "-":
        jj_note = f", default={default_ok}, orphan={orphan_ws_total + orphan_dir_total}"
    print(f"\n{'='*78}\n### round {rnum}  {mode}/{diff}  ->  {quality.upper()}  "
          f"(stale_refs={stale_total}{jj_note}{iso_note})\n{'='*78}")
    if isolate != "-":
        for line in iout.splitlines():
            s = line.strip()
            if s.startswith(("ISOLATED", "ISO_FS", "OVER_ISOLATE", "WORK_LANDED",
                             "WS_NAME", "NAME_PREFIX", "NAME_OK")):
                print("  " + s)
    # show the non-ok lines (failures) + the RESULT/HYGIENE lines
    for line in out.splitlines():
        s = line.strip()
        if (s.startswith("FAIL") or s.startswith("RESULT") or s.startswith("HYGIENE")
                or s.startswith(("STALE_REFS", "DEFAULT_OK", "DEFAULT_STATUS",
                                 "DEFAULT_PARENT", "ORPHAN_WS", "ORPHAN_DIRS",
                                 "WORKSPACE_HYGIENE"))
                or "jj workflow used" in line
                or "advanced through jj" in line):
            print("  " + s)
    # per-agent metrics rows
    for a in rd["reports"]:
        r = a["report"] or {}
        md = r.get("mode_detected", "?")
        mode_ok = "OK" if md == mode else f"WRONG({md})"
        stale = 1 if f"agent-{a['k']}" in stale_set else 0
        orphan_ws = 1 if f"agent-{a['k']}" in orphan_ws_set else 0
        orphan_dirs = 1 if f"agent-{a['k']}" in orphan_dir_set else 0
        tokens = token_map.get((rnum, a["k"]), 0)
        note = f"detect={mode_ok};pub={r.get('published')};mis={str(r.get('mishandled',''))[:40]}"
        sh("bash", f"{HERE}/record-metrics.sh",
           "--round", str(rnum), "--agent", f"agent-{a['k']}", "--mode", mode,
           "--difficulty", diff, "--tier", a["tier"], "--env", env_for.get(mode, "-"),
           "--total", str(r.get("total_seconds", 0) or 0),
           "--conflict", str(r.get("conflict_seconds", 0) or 0),
           "--tokens", str(tokens), "--stale", str(stale), "--isolate", isolate,
           "--orphan-ws", str(orphan_ws), "--orphan-dirs", str(orphan_dirs),
           "--default-ok", default_ok, "--name-ok", name_ok,
           "--retries", str(r.get("retries", 0) or 0),
           "--stalls", str(r.get("stalls", 0) or 0),
           "--quality", quality, "--notes", note)
        print(f"  - a{a['k']} {a['tier']:<5} {a['model']:<7} detect={mode_ok:<10} "
              f"tot={r.get('total_seconds')}s cnf={r.get('conflict_seconds')}s "
              f"tok={tokens} stale={stale} orphan={orphan_ws + orphan_dirs} def={default_ok} "
              f"iso={isolate} name={name_ok} retr={r.get('retries')} stall={r.get('stalls')} "
              f"pub={r.get('published')}")

print(f"\n{'#'*78}\n# SCOREBOARD\n{'#'*78}")
code, out, err = sh("bash", f"{HERE}/scoreboard.sh")
print(out)
if err.strip():
    print("scoreboard stderr:", err)
