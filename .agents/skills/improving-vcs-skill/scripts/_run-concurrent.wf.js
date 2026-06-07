export const meta = {
  name: "vcs-eval-round",
  description:
    "Drive vcs-skill integration sub-agents across (mode x difficulty x tier) cells",
  phases: [{ title: "Integrate" }],
};
// args arrives as a JSON STRING from the Workflow tool — parse defensively.
const A = typeof args === "string" ? JSON.parse(args) : args;

const MODEL = { large: "opus", mid: "sonnet", small: "haiku" };
const FEATURE = {
  1: "streaming export",
  2: "input validation",
  3: "registry refresh",
  4: "retry backoff",
  5: "audit logging",
  6: "rate limiting",
};

// Faithful reproduction of new-sandbox.sh write_brief (integration-only ticket).
function briefFor(k, ticket, feature) {
  return `# Ticket ${ticket} — land "${feature}"

Your change for this ticket is **already written and committed**. In your
workspace it is recorded as \`agent-${k}\` (your team labels each person's finished
work that way). You do **not** need to write any code for this ticket.

Several teammates finished their own tickets at the same time and are landing
them on the shared \`main\` line concurrently. Your one job: get your committed
work (\`agent-${k}\`) onto \`main\` so mainline history contains it alongside
everyone else's, using your team's standard version-control workflow.

Because teammates touched the same files and lines, you will hit merge conflicts
when you integrate. Resolve them by **union — keep everyone's work**: preserve
every teammate's additive change (every changelog entry, every list/array
element, every code block someone added — never drop one). If a single-valued
field (such as a version number) was set differently by two teammates, keep the
**higher** value. Leave no conflict markers.

**This is a version-control exercise, not a coding one.** To keep the test
focused on integration quality:

- Do **not** write new code, add or modify tests, or "improve" anything.
- Do **not** run the app, a build, formatters, or any test suite to verify it.
- Do **not** amend the contents of your committed change.

Follow your version-control guidance all the way through to a clean finished
state — integrate, resolve every conflict by union, publish onto \`main\`, and do
whatever end-of-integration tidy-up that guidance calls for — then **stop**. You
are measured on a fast, correct integration; there is no coding work to do
afterward.`;
}

const REPORT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: [
    "mode_detected",
    "how_detected",
    "total_seconds",
    "conflict_seconds",
    "conflicts_hit",
    "retries",
    "stalls",
    "published",
    "clear",
    "ambiguous",
    "mishandled",
  ],
  properties: {
    mode_detected: {
      type: "string",
      description: "jj or git — what you concluded the repo uses",
    },
    how_detected: {
      type: "string",
      description: "how you determined the VCS mode (the signal you used)",
    },
    total_seconds: {
      type: "integer",
      description: "END-START wall seconds for your whole run",
    },
    conflict_seconds: {
      type: "integer",
      description:
        "seconds from first conflict to resolved+published, 0 if none",
    },
    conflicts_hit: { type: "integer" },
    retries: { type: "integer", description: "VCS steps you had to repeat" },
    stalls: {
      type: "integer",
      description: "times you were stuck / had to re-read guidance",
    },
    published: {
      type: "boolean",
      description:
        "true ONLY if you verified your work is actually on the shared main",
    },
    clear: {
      type: "string",
      description: "what in the vcs skill was clear and worked",
    },
    ambiguous: {
      type: "string",
      description: "what was unclear, missing, or slow in the vcs skill",
    },
    mishandled: {
      type: "string",
      description: 'any conflict you suspect you resolved wrong, or "none"',
    },
  },
};

function buildPrompt(ws, brief) {
  return `You are a coding agent working in a software repository. Your version-control guidance is the team's \`vcs\` skill. Before doing anything else, read it and follow it for every commit, merge, rebase, and publish decision you make:
  - ${A.vcsSkill}
Read \`SKILL.md\` first. Open referenced fallback files only when \`SKILL.md\` says they are needed for your current step; do not pre-read every linked doc.
Do not assume which version-control system is in use — determine it yourself from the repository, exactly as your VCS guidance instructs, before you start. Use ONLY the \`vcs\` skill for version-control guidance; do not consult or invoke any other skill, and do not look outside your workspace except to read the vcs skill files needed for the current step.

Your workspace is: ${ws}
Run integration commands against that workspace (cd into it, or pass -C "${ws}").
Do not edit project files outside that workspace. The only allowed exception is
end-of-integration VCS cleanup that your guidance explicitly prescribes, such as
updating the default jj workspace, forgetting a retired workspace, or removing
the retired workspace directory after its work is on main.

Timing — follow exactly so your run can be measured:
  - Your VERY FIRST action: run \`date +%s\` and remember the number as START.
  - The moment you FIRST observe a merge/rebase conflict: run \`date +%s\` as CFLICT_START (skip if you never hit a conflict).
  - When your work is fully published AND all conflicts are resolved: run \`date +%s\` as END.
  - total_seconds = END - START. conflict_seconds = END - CFLICT_START (0 if you never hit a conflict).

Your task:
${brief}

When finished, return the structured report fields. Be strictly honest: set published=true only if you verified your work is actually on the shared main line, and report any conflict you are unsure you resolved correctly. Your returned fields ARE the result — there is no human reading a prose reply.`;
}

phase("Integrate");
// CONCURRENT integration: within a round, ALL agents integrate at the SAME time,
// contending for `main` (git non-ff retry loop / jj cross-workspace contention).
// Each round's agents run in parallel; rounds also run in parallel. The correct
// union is order-independent, so the oracle scores it regardless of who won races.
function runAgent(rd, k) {
  const tier = rd.tiers[k - 1];
  const ws = `${A.base}/round-${rd.round}/ws-agent-${k}`;
  const ticket = `VCS-${rd.round}-${k}`;
  const brief = briefFor(k, ticket, FEATURE[k]);
  const label = `r${rd.round}-${rd.mode}-${rd.difficulty}-a${k}-${tier}`;
  return agent(buildPrompt(ws, brief), {
    label,
    phase: "Integrate",
    model: MODEL[tier],
    schema: REPORT_SCHEMA,
    agentType: "general-purpose",
  }).then((report) => ({
    round: rd.round,
    mode: rd.mode,
    difficulty: rd.difficulty,
    k,
    tier,
    model: MODEL[tier],
    label,
    report,
  }));
}
// Rounds run concurrently; agents WITHIN a round run concurrently too (the
// contention test). Per-agent OUTPUT tokens come from each agent's transcript
// JSONL in _score.py (exact, mapped by ws-agent path) — concurrency-independent,
// so no budget plumbing here.
const rounds = await parallel(
  A.rounds.map((rd) => async () => {
    const n = rd.tiers.length;
    const reports = await parallel(
      Array.from({ length: n }, (_, i) => () => runAgent(rd, i + 1)),
    );
    return {
      round: rd.round,
      mode: rd.mode,
      difficulty: rd.difficulty,
      reports: reports.filter(Boolean),
    };
  }),
);
return rounds;
