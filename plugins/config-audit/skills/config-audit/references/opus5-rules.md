# What current Claude models need added, and what they need taken away

Distilled from Anthropic's prompt engineering docs (overview, prompting best
practices, and the per-model pages for Opus 5, Sonnet 5, Fable 5, Fable 5.1).
Read this before judging whether a rule in someone's `CLAUDE.md` is still
earning its place.

The single most useful framing comes from the Fable 5 page:

> "Refactor existing prompts and skills. Skills developed for prior models are
> often too prescriptive and can degrade output quality. Review and consider
> removing older instructions if default performance is better."

Most bloated configurations are not missing instructions. They are carrying
instructions written to patch weaknesses the model no longer has.

---

## Take away

### Generic self-verification and re-checking

> "Claude Opus 5 verifies its own work without being told to. If your prompt
> contains explicit verification instructions ('include a final verification
> step for any non-trivial task', 'use a subagent to verify'), remove them:
> instructions like these cause over-verification on Claude Opus 5, and removing
> them reduces wasted tokens with no loss in quality."

> "Avoid instructing re-checks it already performs ('double-check your answer',
> 're-verify before responding'); these compound with the model's own behavior
> and add cost without improving results."

Typical offenders: "never mark a task complete without proving it works",
"challenge your own work before presenting it", "would a staff engineer approve
this?", and any skill built as a generate → critique → improve loop.

**Important distinction.** "Do not claim tests pass without running them" is a
different rule and should be *kept*. See `judgment.md`.

### Instructions to reflect on or narrate reasoning

On Fable 5, prompts that tell the model to echo, transcribe or explain its
internal reasoning can trigger the `reasoning_extraction` refusal category and
force a fallback to an older model. Audit skills for "show your thinking" and
reflection-loop instructions.

### Manual Chain-of-Thought / Tree-of-Thought scaffolding

Adaptive thinking is on by default on Opus 5 and Sonnet 5, and is the only mode
on Fable 5 / 5.1.

> "Prefer general instructions over prescriptive steps. A prompt like 'think
> thoroughly' often produces better reasoning than a hand-written step-by-step
> plan. Claude's reasoning frequently exceeds what a human would prescribe."

### Encouragement to use subagents

The direction of the fix has reversed. Current models over-delegate.

> "Claude Opus 5 delegates to subagents more readily than prior models.
> Delegation pays off on genuinely independent, sizeable tracks of work, but it
> multiplies cost and time when applied to small tasks."

Replace "use subagents liberally" with a condition, and set the deterministic
caps (Claude Code ≥ 2.1.217):

```json
"env": {
  "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "3",
  "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2"
}
```

### Over-prompting and hard thresholds

> "Remove over-prompting. Tools that undertriggered in previous models are
> likely to trigger appropriately now. Instructions like 'If in doubt, use
> [tool]' will cause overtriggering."

> "Where you might have said 'CRITICAL: You MUST use this tool when...', you can
> use more normal prompting like 'Use this tool when...'."

Rules shaped like "enter plan mode for ANY task with 3+ steps" fire constantly.
Describe the condition instead of setting a counter.

### Context-window workarounds

Anything whose stated purpose is saving context — thin subagents that return
one-line summaries, aggressive early compaction, task-count thresholds for
switching modes — was solving a problem that a 1M-token window and server-side
compaction have removed. Read the skill's own justification; these usually
announce themselves.

### Model-selection routers

`effort` is now the documented primary control for the intelligence / latency /
cost trade-off. Hand-rolled "pick a cheaper model for easy tasks" logic is
superseded.

---

## Add

These are the behaviours that current models need steering on, and that most
older configurations have nothing about.

### Response length

Opus 5's visible responses run longer than prior models', and **lowering
`effort` does not reliably shorten them** — effort controls thinking, not
speech. Prompt for length explicitly:

> "Keep responses focused, brief, and concise. Keep disclaimers and caveats
> short, and spend most of the response on the main answer. When asked to
> explain something, give a high-level summary unless an in-depth explanation is
> specifically requested."

### Length of files written to disk

Separate from conversational verbosity, and separately in need of a rule:

> "Match the length of written documents to what the task needs: cover the
> substance, but do not pad with filler sections, redundant summaries, or
> boilerplate."

### Task scope

Opus 5 can quietly widen a task. Fable 5.1 may fix nearby code or commit extra
test files.

> "Deliver what was asked, at the scope intended. Make routine judgment calls
> yourself, and check in only when different readings of the request would lead
> to materially different work. If the request seems mistaken or a better
> approach exists, say so in a sentence and continue with the task as asked
> rather than quietly narrowing, widening, or transforming it."

### Correction narration

> "Only correct an earlier statement when the error would change the user's
> code, conclusions, or decisions. State corrections plainly and briefly, then
> continue the task."

### Evidence behind progress claims

The one verification-shaped instruction that is still endorsed, from Fable 5:

> "Before reporting progress, audit each claim against a tool result from this
> session. Only report work you can point to evidence for; if something is not
> yet verified, say so explicitly. Report outcomes faithfully: if tests fail,
> say so with the output; if a step was skipped, say that; when something is
> done and verified, state it plainly without hedging."

---

## Structural rules for skills

- **SKILL.md is a router, not a manual.** Its body loads in full the moment the
  skill is invoked. Put detail in `references/` and have SKILL.md say which file
  answers which question. A 456 KB SKILL.md costs roughly 114,000 tokens per
  invocation.
- **`description:` is the routing prompt.** A skill without one is invisible and
  can never be invoked. Write what it does *and* when to use it, including the
  literal phrases a user would type.
- **Claude Code reads only `name` and `description` from frontmatter.** A custom
  `trigger:` key is inert; fold its content into `description`.
- **A custom skill shadows a built-in one of the same name.** Check for
  collisions before naming.
- **Prefer plugins to installers.** A plugin can be updated and uninstalled. An
  `install.sh` that copies files into `$HOME/.claude` leaves them there forever.
