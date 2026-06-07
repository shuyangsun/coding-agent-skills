export const meta = {
  name: "vcs-eval-start-round",
  description:
    "Drive vcs-skill SESSION-START isolation sub-agents (single agent per mode x arm x tier cell)",
  phases: [{ title: "Start" }],
};
// args arrives as a JSON STRING from the Workflow tool — parse defensively.
const A = typeof args === "string" ? JSON.parse(args) : args;

const MODEL = { large: "opus", mid: "sonnet", small: "haiku" };

// Each start round is SINGLE-agent: the agent is dropped into a shared repo, must
// author one tiny specified edit and land it on `main`, and (the thing under
// test) ISOLATE first — its own worktree (git) / workspace (jj) before working.
// The brief is provided verbatim from new-sandbox.sh's briefs/agent-1.md (passed
// in `args`, so the deterministic start-instructions stay single-sourced) — this
// runner does NOT reconstruct it. Score afterward with check-isolation.sh +
// check-quality.sh (or _score.py, which runs both).

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
        "seconds resolving any conflict, 0 if none (start rounds rarely conflict)",
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
        "true ONLY if you verified your change is actually on the shared main",
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
      description: 'anything you suspect you did wrong, or "none"',
    },
  },
};

// `startPath` is baked into the prompt so _score.py can map the agent's transcript
// back to its round for the per-agent token count (same `round-<N>/ws-agent-<k>`
// or repo path convention the integration runners rely on).
function buildPrompt(startPath, brief, assignedPath) {
  const assigned =
    assignedPath && assignedPath !== startPath
      ? `\nYour assigned workspace is: ${assignedPath}\nIf your starting point is different from the assigned workspace, move to the assigned workspace before any edit, commit, branch/bookmark change, or publish.\n`
      : "";
  return `You are a coding agent working in a software repository. Your version-control guidance is the team's \`vcs\` skill. Before doing anything else, read it and follow it for every commit, branch, merge, and publish decision you make:
  - ${A.vcsSkill}
Read \`SKILL.md\` first. Open referenced fallback files only when \`SKILL.md\` says they are needed for your current step; do not pre-read every linked doc.
Do not assume which version-control system is in use — determine it yourself from the repository, exactly as your VCS guidance instructs, before you start. Use ONLY the \`vcs\` skill for version-control guidance; do not consult or invoke any other skill, and do not look outside your starting area except to read the vcs skill files needed for the current step.

Your starting point is: ${startPath}
Run your version-control commands from there. Several teammates are working in this same repository on this machine at the same time; follow your VCS guidance for how to set yourself up before you start changing files.
${assigned}

Timing — follow exactly so your run can be measured:
  - Your VERY FIRST action: run \`date +%s\` and remember the number as START.
  - When your change is fully published on the shared main: run \`date +%s\` as END.
  - total_seconds = END - START. conflict_seconds = 0 unless you actually hit a conflict.

Your task:
${brief}

When finished, return the structured report fields. Be strictly honest: set published=true only if you verified your change is actually on the shared main line. Your returned fields ARE the result — there is no human reading a prose reply.`;
}

phase("Start");
// Single agent per round; rounds run concurrently with each other. Each round:
//   { round, mode, tier, startPath, brief }
const rounds = await parallel(
  A.rounds.map((rd) => async () => {
    const label = `r${rd.round}-${rd.mode}-start-${rd.startFrom || "main"}-${rd.tier}`;
    const report = await agent(
      buildPrompt(rd.startPath, rd.brief, rd.assignedPath),
      {
        label,
        phase: "Start",
        model: MODEL[rd.tier],
        schema: REPORT_SCHEMA,
        agentType: "general-purpose",
      },
    );
    return {
      round: rd.round,
      mode: rd.mode,
      difficulty: "easy",
      reports: [{ k: 1, tier: rd.tier, model: MODEL[rd.tier], label, report }],
    };
  }),
);
return rounds;
