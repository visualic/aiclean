---
name: config-audit
description: Audit and clean up a Claude Code setup against Anthropic's current prompt-engineering guidance. Finds stale scaffolding in CLAUDE.md (self-verification instructions, subagent encouragement, manual chain-of-thought, hard trigger thresholds), oversized SKILL.md files that cost tens of thousands of tokens per invocation, skills with no description that can never be routed to, duplicate and dead hooks in settings.json, skills that depend on an MCP server or API key that is not configured, broken cross-references, and skills that have never once been invoked. Reports findings and asks before changing anything; archives rather than deletes. Use on /config-audit, or for requests like "내 클로드 설정 점검해줘", "스킬 정리해줘", "설정 최적화", "audit my Claude setup", "why is my context so full", "clean up my skills".
---

# Claude config audit

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
python3 <skill-dir>/scripts/inventory.py   # sizes, frontmatter, routing cost
python3 <skill-dir>/scripts/usage.py       # real invocations from session logs
python3 <skill-dir>/scripts/health.py      # hooks, dead deps, broken refs
```

`--json` on any of them for machine-readable output.

### 3. Read CLAUDE.md against the guidance

Read `~/.claude/CLAUDE.md` and check it against `references/opus5-rules.md`.
Look for instructions to **remove** (generic self-verification, "use subagents
liberally", manual CoT, hard thresholds like "ANY task with 3+ steps",
ALL-CAPS forcing, duplicate memory systems) and instructions to **add**
(response length, written-document length, task scope, correction narration,
evidence behind progress claims).

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

- skills that cannot run (no description, missing MCP server, missing keys)
- oversized `SKILL.md` — give the per-invocation token cost
- duplicate hooks, dead hook paths
- custom skills shadowing a built-in
- stale `CLAUDE.md` instructions, quoting the guidance
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
| `references/opus5-rules.md` | What current models need added and removed, with the source quotes |
| `references/judgment.md` | How the evidence misleads; eight real traps; the keep/archive decision |
| `references/claude-md-template.md` | Drop-in working-practice block, and what it deliberately omits |

## Scope

This audits the user-level setup at `~/.claude`. Project-level `.claude/`
directories inside repositories are a separate question — mention them if the
inventory suggests they matter, but changing a repository's committed
configuration affects anyone else working in it, so raise it rather than
deciding it.
