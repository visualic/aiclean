# Judgment: how to read the evidence, and how it misleads you

`inventory.py`, `usage.py` and `health.py` produce facts. Deciding what to keep
is not a fact, and this is where an audit goes wrong.

Every trap below was hit for real, in the audit this skill was built from or
in a later run of it. Each one produced a confident, wrong conclusion that had
to be walked back.

---

## Trap 1 — "grep the transcripts" measures nothing

Every session's system prompt contains the full list of installed skills. So
`grep -rl "<skill>" ~/.claude/projects/**/*.jsonl` matches almost every
transcript, for every skill, including ones that have never run.

The tell: **every skill returns the same number.** During the original audit this
came back as 861 sessions for all eleven skills checked — a number that looked
like heavy usage and meant nothing.

Only `tool_use` blocks are evidence:

```
{"name":"Skill","input":{"skill":"<name>"}}
{"name":"Task","input":{"subagent_type":"<name>"}}
```

`usage.py` counts only these. Do not fall back to grep.

## Trap 2 — a zero invocation count can be an artifact

A skill with no `description:` frontmatter is listed under the first non-empty
line of its body, plus any `when_to_use`. Read what that line actually is. A bare
heading like `# deploy-helper` gives the router almost nothing to match on, and
then the skill's zero is weak evidence. A first line that already says what the
skill does and when may route fine. (Before Claude Code 2.1.69, project skills
without a description were not listed at all.)

In the original audit, eight skills had no description. Fixing their frontmatter
and *then* judging them by usage would have been circular — they had never had a
real chance to be used. They had to be judged on content instead.

A rename resets the count the same way. Transcripts record the name a skill had
when it ran, so after gstack's `skill_prefix` turned `codex` into
`gstack-codex`, a skill used that week read as never invoked. `usage.py` now
matches names across a toolkit prefix and lists those under "used under another
name". A rename it cannot see, such as a hand-renamed skill, still reads as zero.

**Rule: cross-check every zero against `inventory.py`'s "no description" list
and against any recent rename before treating it as a signal.**

## Trap 3 — the name is not the content

`verification-before-completion` reads like exactly the self-verification
scaffolding the Opus 5 guide says to delete. It was queued for archiving twice
on that basis.

Opening it showed something else: an evidence-before-claiming rule. *Do not say
tests pass without running them.* That is not a self-critique loop — it is the
pattern the Fable 5 guide explicitly recommends ("audit each claim against a
tool result from this session"). It was kept.

By contrast, `reflection` — a literal generate → critique → improve loop, capped
at three iterations — was the real instance of the anti-pattern, and went.

**Rule: open the file. Classify on what it does, never on what it is called.**

## Trap 4 — the anti-pattern scan has a noisy channel

Scanning skill bodies for legacy markers works for some signals and not others:

| signal | useful? |
|---|---|
| context-saving justifications ("compaction required at N tasks") | yes, decisive |
| manual CoT / ToT scaffolding | yes |
| generate→critique→improve loops (no new input or evidence — see `model-rules.md`) | yes |
| hand-rolled agent messaging protocols | yes |
| **counting 반드시 / MUST / CRITICAL** | **no — matched almost every skill, good ones included** |

Use forced-instruction density as a *cleanup* target (soften the language), not
as grounds for removal.

## Trap 5 — a skill can be dead because of something outside it

Two skills looked fine and could not run at all:

- one routed documentation lookups through an MCP server that was not configured
  on the machine;
- one parallelised four search APIs, none of whose keys were in the environment.

Neither is visible from the skill's own text. `health.py` checks for this.
Beware the inverse too: harness-provided servers (`conductor`,
`claude-in-chrome`) never appear in any settings file, so their absence there
means nothing.

## Trap 6 — archiving a skill breaks things you did not grep for

Removing a skill leaves dangling references. Checking only `SKILL.md` is not
enough. Real breakage was found in:

- `references/*.md` and `templates/*.md` inside other skills
- `commands/*.md`
- agent definition files
- a Python helper script with a skill registry in it
- relative links into the removed skill's own `references/` directory

Sweep `skills/`, `agents/` and `commands/` for `skills/<name>/`, `/<name>`, and
`skill: "<name>"`, then re-run until clean. Where a removed skill owned a file
another skill linked to, rescue that file rather than breaking the link.

## Trap 7 — provenance explains more than any single file

The decisive finding in the original audit was not in any skill. It was that
`~/.claude/skills/` was largely one abandoned product's bundled catalogue: its
installer set `GLOBAL_CLAUDE_DIR="$HOME/.claude"` and rsynced 35 skills and 19
agents in. The product was shelved; the skills stayed for seven months.

Once that was clear, dozens of individually ambiguous skills resolved at once.

**Worth checking:** do many skills share a creation timestamp to the minute? Do
they share a section template? Is there an installer somewhere on disk that
writes to `$HOME/.claude`? Does the shell history around that timestamp explain
what was being built?

## Trap 8 — a custom skill can shadow a better built-in

A custom `code-review` skill was hiding Claude Code's built-in one, which
supports effort levels, `--fix`, `--comment` and a multi-agent cloud review.
Archiving the custom copy *restored* capability.

**Rule: check every custom skill name against the built-in list.**

## Trap 9 — a skill unused here can be in daily use by another tool

gstack showed two invocations in two months of Claude Code transcripts, and
its archive was one step from running. Then the other harness homes turned up:
`~/.codex/skills/gstack*` were symlinks into `~/.claude/skills/gstack`, and
Codex sessions had read `gstack-review` 2,213 times in the same window.
Archiving the directory would have broken the tool the user relied on most.
Removing only the Claude-side entries would not have held either: gstack's
upgrade reinstalls them.

`usage.py` reads Claude's transcripts only. It now lists skills that another
tool's home links into under "shared with another tool" and marks them in
the never-invoked list.

**Rule: before archiving, check for links from other tools' homes. A shared
skill's zero here says nothing about its use there.**

---

## Deciding: three questions

For each skill, in order.

**1. Can it run?** Missing MCP server, missing credentials, broken paths, no
SKILL.md → it is already dead. Fix or archive; there is no third option. A
missing description is not death; judge it by the line the router sees instead
(Trap 2).

**2. Does it substitute for something the model now does natively?** Manual
reasoning scaffolds, self-critique loops, context-saving orchestration, agent
messaging protocols, "how to write good \<language\>" guides, step-by-step
walkthroughs for reading charts or screenshots. These do not just
fail to help — the guidance says they can degrade output. Archive.

**3. Is it used, or does it encode something the model cannot know?** Real
invocations, or domain knowledge with no substitute: a specific failure mode, a
house style, a deployment procedure, a distinctive method. Keep.

Anything left over is genuinely the user's call. Present it; do not decide it.

---

## Rules of operation

- **Archive, never delete.** `mv` into `skills-archive/`, and write down why.
  Restoring is then one command.
- **Back up before the first move.** A dated tar of `skills/`, `agents/`,
  `CLAUDE.md` and both settings files.
- **Report before acting.** The user's setup is theirs. Findings first, then ask.
- **Re-verify after every batch**, not at the end. Broken references compound.
- **Say when you were wrong.** This file exists because several confident calls
  during the original audit were wrong, and catching them mattered more than any
  individual deletion.
