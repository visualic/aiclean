# aiclean

Audit and clean up a Claude Code setup against Anthropic's current
prompt-engineering guidance.

Most `~/.claude` directories drift the same way. They accumulate instructions
written to patch weaknesses the models no longer have, plus skills installed
once and never used. Both cost tokens on every session, and some of it actively
degrades output — the guidance is explicit that older, over-prescriptive skills
"can degrade output quality."

This skill finds it and asks before touching anything.

## Install

### Claude Code

```
/plugin marketplace add visualic/aiclean
/plugin install aiclean@visualic
```

### Codex CLI and other harnesses

```sh
git clone https://github.com/visualic/aiclean.git ~/aiclean
cd ~/aiclean && ./install.sh
```

Links the skill into every harness home it finds (`~/.codex`, `~/.agents`,
`~/.cursor`, `~/.gemini`, `~/.hermes`). Because it links rather than copies,
`git pull` updates all of them at once. `./install.sh --list` shows what it
would touch; `./install.sh --uninstall` removes it cleanly.

## Use

Open a session and ask:

> 내 클로드 설정 점검해줘

or run `/aiclean` in Claude Code.

It gathers evidence, reports findings, and waits. Nothing is changed without
your say-so, nothing is deleted — approved removals are moved to
`~/.claude/skills-archive/` with the reason written down, so restoring is one
`mv`.

## What it checks

**CLAUDE.md** — instructions that current guidance says to remove (generic
self-verification, "use subagents liberally", manual chain-of-thought, "think
carefully before answering", hard thresholds like "ANY task with 3+ steps",
duplicate memory systems, re-approval of routine steps inside an approved
scope), effort pinned at a level tuned for an older model, and the ones most
files are missing (response length, written-document length, task scope,
correction narration, evidence behind progress claims). Also rules that
contradict each other across `CLAUDE.md` and the skills that load with it — a
confirm-before-pushing policy next to a skill that pushes on its own — reported
with both sides quoted.

**Skills and agents** — `SKILL.md` bodies large enough to cost tens of thousands
of tokens per invocation; skills with no `description:`, which the router sees
only by the first line of the body — often a bare heading; agents that share a
`name`, of which only one loads; inert custom frontmatter keys; custom skills
shadowing a built-in.

**Hooks** — duplicate registrations that fire twice, and hooks pointing at paths
that no longer exist.

**Dependencies** — skills that route through an MCP server or an API key that is
not configured on this machine. These look healthy from the inside and cannot
run.

**References** — links to skills that are no longer installed, including the ones
that hide in `references/`, `templates/`, README files and helper scripts.

**Project-level configuration** — `.claude/` directories committed inside
repositories. When a toolkit is installed both globally and into a repo, the
project copy is usually the older one: a same-name skill in it is shadowed by
the global copy, while a same-name agent overrides it. Git worktrees multiply
this: every worktree of a repo carries its own copy, so one stale commit becomes
dozens of directories. Reported, never edited — it is committed configuration
that affects everyone working in the repo.

**Usage** — real `Skill` and subagent invocations parsed from session
transcripts. Not a grep: every session's system prompt lists every skill, so
grepping returns the same number for everything and means nothing. Skills that
another tool's home (`~/.codex`, `~/.agents`, ...) links into are set apart,
since their use there never shows up in Claude's transcripts.

## What it will not do

Decide for you. The scripts produce facts; the keep-or-archive call needs
judgment, and `references/judgment.md` is mostly a record of how that judgment
goes wrong — nine traps, each one a confident wrong conclusion from the audit
this was built from. The most useful is the simplest: a skill's name is not its
contents, so open the file.

## Layout

```
.claude-plugin/marketplace.json          Claude Code marketplace definition
install.sh                               installer for non-plugin harnesses
plugins/aiclean/
  .claude-plugin/plugin.json
  skills/aiclean/
    SKILL.md                             the procedure
    scripts/inventory.py                 sizes, frontmatter, routing cost
    scripts/usage.py                     real invocations from session logs
    scripts/health.py                    hooks, dead deps, broken references
    scripts/workspaces.py                project-level .claude/ copies
    references/model-rules.md            guidance distilled, with source quotes
    references/judgment.md               how the evidence misleads you
    references/claude-md-template.md     drop-in working-practice block
```

The scripts run standalone if you would rather read the numbers yourself:

```sh
python3 plugins/aiclean/skills/aiclean/scripts/inventory.py
python3 plugins/aiclean/skills/aiclean/scripts/usage.py
python3 plugins/aiclean/skills/aiclean/scripts/health.py
python3 plugins/aiclean/skills/aiclean/scripts/workspaces.py
```

All four take `--root` and `--json`.

## Sources

Anthropic's prompt engineering documentation: the
[overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview),
[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
and the per-model pages for
[Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5),
[Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5),
[Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5),
[Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
and
[Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1);
the [effort](https://platform.claude.com/docs/en/build-with-claude/effort) page;
and Claude Code's [skills](https://code.claude.com/docs/en/skills) and
[subagents](https://code.claude.com/docs/en/sub-agents) references for
frontmatter keys and name precedence.

## License

MIT
