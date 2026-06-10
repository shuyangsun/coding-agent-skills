# issues/

Documented failure modes observed while coding agents drove version control through
the `vcs` skill — mostly Jujutsu multi-workspace lifecycle traps (stale `default`
workspace, agents not isolating, degenerate empty merges, cross-agent work bleed,
orphaned side-heads, guard-hook cwd drift). Each issue grounds a fix in `vcs` or a
gate in `improving-vcs-skill`; several are cross-linked to the [plans](../plans/OVERVIEW.md)
and [benchmarks](../benchmarks/OVERVIEW.md) that act on them.

Naming: `YYYY-MM-DD/NNNN-slug.md`, `NNNN` unique across the whole `issues/` tree.

## Issues

### 2026-06-06

- [`0001` — jj default workspace goes stale, blocking collaboration](2026-06-06/0001-jj-default-workspace-goes-stale-blocking-collaboration.md)

### 2026-06-07

- [`0002` — agent used `default` jj workspace instead of isolating](2026-06-07/0002-agent-used-default-jj-workspace-instead-of-isolating.md)
- [`0003` — `integrate.sh` forms a degenerate empty merge, can't push](2026-06-07/0003-jj-integrate-forms-degenerate-empty-merge-blocking-push.md)
- [`0004` — benchmark created a jj workspace but never used it](2026-06-07/0004-benchmark-created-jj-workspace-but-never-used-it.md)
- [`0005` — concurrent agent committed & pushed another agent's work](2026-06-07/0005-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md)
- [`0006` — agent inspected another agent's workspace during cleanup](2026-06-07/0006-agent-inspected-and-asked-about-another-agents-workspace-during-cleanup.md)
- [`0007` — workspace cleanup left an unreferenced empty side-head](2026-06-07/0007-workspace-cleanup-left-unreferenced-empty-side-head.md)
- [`0008` — vcs guard hook traps agent on cwd drift / unmarked workspaces](2026-06-07/0008-vcs-guard-hook-cwd-drift-and-missing-owner-marker-trap.md)

### 2026-06-09

- [`0009` — vcs hook refuses read-only Bash after Claude Code resets cwd to shared workspace](2026-06-09/0009-vcs-hook-refuses-read-only-bash-after-claude-cwd-reset.md)
