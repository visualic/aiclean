---
name: aiclean
description: Audit and clean up a Claude Code setup against Anthropic's current prompt-engineering guidance. Finds stale scaffolding in CLAUDE.md (self-verification instructions, subagent encouragement, manual chain-of-thought, hard trigger thresholds), rules in CLAUDE.md and skills that contradict each other, oversized SKILL.md files that cost tens of thousands of tokens per invocation, skills with no description that the router can barely see, duplicate and dead hooks in settings.json, skills that depend on an MCP server or API key that is not configured, broken cross-references, and skills that have never once been invoked. Reports findings and asks before changing anything; archives rather than deletes. Use on /aiclean, or for requests like "내 클로드 설정 점검해줘", "스킬 정리해줘", "설정 최적화", "audit my Claude setup", "why is my context so full", "clean up my skills".
---

# aiclean

Audit `~/.claude` — `CLAUDE.md`, skills, agents, hooks — against Anthropic's
current prompt-engineering guidance, and clean up what no longer earns its
place.

Most setups are not missing instructions. They are carrying instructions written
to patch weaknesses current models no longer have, plus skills installed once and
never used. Both cost tokens on every session.

## Ground rules

1. **Report before acting.** Produce findings, show them, ask. The user decides.
2. **Archive, never delete.** `mv` into `skills-archive/`, and write down why.
3. **Back up first**, before the first move.
4. **Open the file before judging it.** Names mislead — see `references/judgment.md`.
5. **Re-verify after every batch.** Broken references compound.

## Procedure

### 1. Back up

```sh
TS=$(date +%Y%m%d-%H%M%S); BK=~/.claude/backups/audit-$TS; mkdir -p "$BK"
cd ~/.claude && cp CLAUDE.md settings.json "$BK/" 2>/dev/null
cp settings.local.json "$BK/" 2>/dev/null
tar czf "$BK/skills.tar.gz" skills 2>/dev/null
tar czf "$BK/agents.tar.gz" agents 2>/dev/null
echo "$BK"
```

### 2. Gather facts

Run all three; they are independent.

```sh
python3 <skill-dir>/scripts/inventory.py    # sizes, frontmatter, routing cost
python3 <skill-dir>/scripts/usage.py        # real invocations from session logs
python3 <skill-dir>/scripts/health.py       # hooks, dead deps, broken refs
python3 <skill-dir>/scripts/workspaces.py   # project-level .claude/ copies
```

`--json` on any of them for machine-readable output. `workspaces.py` takes
repeatable `--root` if the user's checkouts live somewhere unusual.

### 3. Read CLAUDE.md against the guidance

Read `~/.claude/CLAUDE.md` and check it against `references/model-rules.md`.
Look for instructions to **remove** (generic self-verification, "use subagents
liberally", manual CoT, "think carefully before answering", "write out your
reasoning", hard thresholds like "ANY task with 3+ steps", ALL-CAPS forcing,
duplicate memory systems) and instructions to **add** (response length,
written-document length, task scope, correction narration, evidence behind
progress claims).

Also check `settings.json` for `effortLevel`, a per-model level under
`modelSettings`, or `env.CLAUDE_CODE_EFFORT_LEVEL` pinned at `high` or above —
a carry-over from Opus 5 that costs more on Opus 5.5.

`references/claude-md-template.md` has a drop-in replacement block. Keep the
user's project-specific sections — API key tables, service quirks, house
conventions — untouched. Those are the most valuable part of the file.

### 4. Judge each skill

Read `references/judgment.md` first. It records the traps that produced wrong
conclusions during the audit this skill came from, and the three questions to
ask about each skill.

Short version: can it run at all → does it substitute for something the model
now does natively → is it used, or does it encode something the model cannot
know. Anything left over is the user's call to make, not yours.

### 5. Present findings, then act on what is approved

Group by severity. Lead with things that are broken or free wins:

- skills that cannot run (no SKILL.md, missing MCP server, missing keys)
- skills with no description — listed only by their first body line
- oversized `SKILL.md` — give the per-invocation token cost
- duplicate hooks, dead hook paths
- custom skills shadowing a built-in
- stale `CLAUDE.md` instructions, quoting the guidance
- effort pinned for an older model — as a question
- never-invoked skills — as a question, with the Trap 2 caveat applied

### 6. Clean up after every removal

Archiving a skill leaves dangling references. Sweep `skills/`, `agents/` and
`commands/` for `skills/<name>/`, `/<name>` and `skill: "<name>"`, including
`references/`, `templates/`, README files and helper scripts. Rescue any file
the removed skill owned that something else links to. Re-run `health.py` until
broken references reach zero.

### 7. Verify and record

Confirm: settings JSON still parses, no dead hook paths, no broken references,
every remaining skill has a description. Report the before/after routing cost.

Write the reasoning into `skills-archive/README.md` — what was archived, why,
and the one-line restore command. Six months from now that file is the only
thing standing between the user and re-adding what was removed.

## Reference files

| File | Contents |
|---|---|
| `references/model-rules.md` | What current models need added and removed, with the source quotes |
| `references/judgment.md` | How the evidence misleads; eight real traps; the keep/archive decision |
| `references/claude-md-template.md` | Drop-in working-practice block, and what it deliberately omits |

## Project-level configuration

`workspaces.py` finds `.claude/` directories inside repositories. Report what it
finds; do not edit them. A project's `.claude/` is committed configuration, and
changing it affects everyone else working in that repo.

Two things make this worth raising rather than skipping:

**Double installs.** When a toolkit is installed both globally and into a repo,
the project copy is a snapshot from whenever its installer ran, so it is usually
the older one. What happens next depends on the kind. A same-name *skill* resolves
to the personal copy, so the project copy is dead weight that someone may edit
without effect; project-only skills still add to the routing list. A same-name
*agent* resolves to the project copy, so the older one is what actually runs.

**Worktrees multiply it.** Conductor workspaces, `git worktree add`, or any
setup that gives each task its own checkout means every worktree of a repo
carries its own copy. One stale commit becomes dozens of directories.
`workspaces.py` groups identical skill sets so this reads as one finding.

Also separate the two things it reports. Toolkit copies (dozens of identically
named skills across many repos) are usually leftovers. Hand-written domain
agents — a content writer, an SEO strategist, a release checker — are
deliberate, valuable, and must not be swept up with them. Read before
suggesting.

## Scope

This skill changes only the user-level setup at `~/.claude`, and only with
approval. Everything else it reports.
