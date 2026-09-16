# claude-config-audit

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
/plugin marketplace add visualic/claude-config-audit
/plugin install config-audit@visualic
```

### Codex CLI and other harnesses

```sh
git clone https://github.com/visualic/claude-config-audit.git ~/claude-config-audit
cd ~/claude-config-audit && ./install.sh
```

Links the skill into every harness home it finds (`~/.codex`, `~/.agents`,
`~/.cursor`, `~/.gemini`, `~/.hermes`). Because it links rather than copies,
`git pull` updates all of them at once. `./install.sh --list` shows what it
would touch; `./install.sh --uninstall` removes it cleanly.

## Use

Open a session and ask:

> 내 클로드 설정 점검해줘

or run `/config-audit` in Claude Code.

It gathers evidence, reports findings, and waits. Nothing is changed without
your say-so, nothing is deleted — approved removals are moved to
`~/.claude/skills-archive/` with the reason written down, so restoring is one
`mv`.

## What it checks

**CLAUDE.md** — instructions that current guidance says to remove (generic
self-verification, "use subagents liberally", manual chain-of-thought, hard
thresholds like "ANY task with 3+ steps", duplicate memory systems) and the ones
most files are missing (response length, written-document length, task scope,
correction narration, evidence behind progress claims).

**Skills and agents** — `SKILL.md` bodies large enough to cost tens of thousands
of tokens per invocation; skills with no `description:`, which the router cannot
see and which therefore can never be invoked; inert custom frontmatter keys;
custom skills shadowing a built-in.

**Hooks** — duplicate registrations that fire twice, and hooks pointing at paths
that no longer exist.

**Dependencies** — skills that route through an MCP server or an API key that is
not configured on this machine. These look healthy from the inside and cannot
run.

**References** — links to skills that are no longer installed, including the ones
that hide in `references/`, `templates/`, README files and helper scripts.

**Usage** — real `Skill` and subagent invocations parsed from session
transcripts. Not a grep: every session's system prompt lists every skill, so
grepping returns the same number for everything and means nothing.

## What it will not do

Decide for you. The scripts produce facts; the keep-or-archive call needs
judgment, and `references/judgment.md` is mostly a record of how that judgment
goes wrong — eight traps, each one a confident wrong conclusion from the audit
this was built from. The most useful is the simplest: a skill's name is not its
contents, so open the file.

It also stays out of project-level `.claude/` directories inside repositories.
Those are committed configuration and changing them affects everyone else
working in the repo, so it raises them rather than editing them.

## Layout

```
.claude-plugin/marketplace.json          Claude Code marketplace definition
install.sh                               installer for non-plugin harnesses
plugins/config-audit/
  .claude-plugin/plugin.json
  skills/config-audit/
    SKILL.md                             the procedure
    scripts/inventory.py                 sizes, frontmatter, routing cost
    scripts/usage.py                     real invocations from session logs
    scripts/health.py                    hooks, dead deps, broken references
    references/opus5-rules.md            guidance distilled, with source quotes
    references/judgment.md               how the evidence misleads you
    references/claude-md-template.md     drop-in working-practice block
```

The scripts run standalone if you would rather read the numbers yourself:

```sh
python3 plugins/config-audit/skills/config-audit/scripts/inventory.py
python3 plugins/config-audit/skills/config-audit/scripts/usage.py
python3 plugins/config-audit/skills/config-audit/scripts/health.py
```

All three take `--root` and `--json`.

## Sources

Anthropic's prompt engineering documentation: the
[overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview),
[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
and the per-model pages for
[Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5),
[Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5),
[Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
and
[Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).

## License

MIT
