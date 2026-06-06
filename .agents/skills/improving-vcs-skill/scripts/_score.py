#!/usr/bin/env python3
"""Process a vcs-eval workflow result: score each round objectively, record one
metrics row per agent (round-level quality verdict, per the harness design),
then print the scoreboard. Usage: _score.py <result.json> <harness-base>"""
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
result_path, base = sys.argv[1], sys.argv[2]
rounds = json.load(open(result_path))

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
    print(f"\n{'='*78}\n### round {rnum}  {mode}/{diff}  ->  {quality.upper()}\n{'='*78}")
    # show the non-ok lines (failures) + the RESULT line
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("FAIL") or s.startswith("RESULT") or "jj workflow used" in line or "advanced through jj" in line:
            print("  " + s)
    # per-agent metrics rows
    for a in rd["reports"]:
        r = a["report"] or {}
        md = r.get("mode_detected", "?")
        mode_ok = "OK" if md == mode else f"WRONG({md})"
        note = f"detect={mode_ok};pub={r.get('published')};mis={str(r.get('mishandled',''))[:40]}"
        sh("bash", f"{HERE}/record-metrics.sh",
           "--round", str(rnum), "--agent", f"agent-{a['k']}", "--mode", mode,
           "--difficulty", diff, "--tier", a["tier"], "--env", env_for.get(mode, "-"),
           "--total", str(r.get("total_seconds", 0) or 0),
           "--conflict", str(r.get("conflict_seconds", 0) or 0),
           "--retries", str(r.get("retries", 0) or 0),
           "--stalls", str(r.get("stalls", 0) or 0),
           "--quality", quality, "--notes", note)
        print(f"  - a{a['k']} {a['tier']:<5} {a['model']:<7} detect={mode_ok:<10} "
              f"tot={r.get('total_seconds')}s cnf={r.get('conflict_seconds')}s "
              f"hit={r.get('conflicts_hit')} retr={r.get('retries')} stall={r.get('stalls')} "
              f"pub={r.get('published')}")

print(f"\n{'#'*78}\n# SCOREBOARD\n{'#'*78}")
code, out, err = sh("bash", f"{HERE}/scoreboard.sh")
print(out)
if err.strip():
    print("scoreboard stderr:", err)
