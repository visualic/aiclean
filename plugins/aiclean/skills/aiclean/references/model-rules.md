# What current Claude models need added, and what they need taken away

Distilled from Anthropic's prompt engineering docs (overview, prompting best
practices, and the per-model pages for Opus 5, Opus 5.5, Sonnet 5, Fable 5,
Fable 5.1).
Read this before judging whether a rule in someone's `CLAUDE.md` is still
earning its place.

The single most useful framing comes from the Fable 5 page. It is written about
Fable 5, but every later per-model page repeats the pattern of removing
instructions the model no longer needs:

> "Refactor existing prompts and skills. Skills developed for prior models are
> often too prescriptive for Claude Fable 5 and can degrade output quality.
> Review and consider removing older instructions if default performance is
> better."

Most bloated configurations are not missing instructions. They are carrying
instructions written to patch weaknesses the model no longer has.

---

## Take away

### Generic self-verification and re-checking

> "Claude Opus 5 verifies its own work without being told to. If your prompt
> contains explicit verification instructions ('include a final verification
> step for any non-trivial task,' 'use a subagent to verify'), remove them:
> instructions like these cause over-verification on Claude Opus 5, and removing
> them reduces wasted tokens with no loss in quality."

> "Avoid instructing re-checks it already performs ('double-check your answer,'
> 're-verify before responding'); like verification instructions, these compound
> with the model's own behavior and add cost without improving results."

Typical offenders: "never mark a task complete without proving it works",
"challenge your own work before presenting it", "would a staff engineer approve
this?", and any skill built as a generate → critique → improve loop: the same
output fed back through a critique pass with no new input, criteria or evidence,
repeated until it looks right.

**Important distinction.** "Do not claim tests pass without running them" is a
different rule and should be *kept*. See `judgment.md`.

**Also not the same thing: independent review.** A check that brings something
the author did not have — a completion condition or spec to check against, tests
or tool output the author never ran, a different model — and runs once at a
defined point is not a re-check the model already performs. The Opus 5.5 guide
recommends one for unattended loops:

> "You can also state the completion condition up front and have a separate,
> smaller model check the conversation against it at each end of turn, …"

Judge a review skill by what it adds, not by which model runs it. A different
model looping over the author's own conclusions with nothing new is still a loop.

### Instructions to reflect on or narrate reasoning

On Fable 5 and Opus 5.5, prompts that tell the model to echo, transcribe or
explain its internal reasoning can trigger the `reasoning_extraction` refusal
category, and server-side fallback returns these declines to the caller rather
than retrying them. Audit skills for "show your thinking", "write out your reasoning before
answering" and reflection-loop instructions.

> "If your prompts ask the model to write out its reasoning in the response,
> remove those instructions, set `display: "summarized"`, and read the
> summarized reasoning from the thinking blocks instead; …"


### Manual Chain-of-Thought / Tree-of-Thought scaffolding

Adaptive thinking is on by default on Opus 5 and Sonnet 5, and is the only mode
on Fable 5 / 5.1.

> "Prefer general instructions over prescriptive steps. A prompt like 'think
> thoroughly' often produces better reasoning than a hand-written step-by-step
> plan. Claude's reasoning frequently exceeds what a human would prescribe."

On Opus 5.5 even the general version is superseded — thinking is always on and
the model decides how much to do. The guide says this about chat system prompts:

> "In chat applications, if your system prompt contains instructions that tell
> Claude to think carefully before answering, consider removing them for Claude
> Opus 5.5. The model decides for itself how much to think, and effort is the
> main control."

Anthropic measured removing such a line in a chat product: replies started
sooner with no clear quality loss. For a coding agent the same conclusion rests
on the effort docs rather than that measurement:

> "Adaptive thinking is always on and can't be turned off, so effort is the
> primary control for how much the model reasons and what a request costs."

The inverse holds too — "answer quickly, don't overthink" is a weaker lever than
lowering effort:

> "To get less thinking, lower the effort level first. Lowering effort reduces
> thinking, and with it cost and latency, more reliably than prompt
> instructions do."

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

### Model-selection routers, and effort pinned for an older model

`effort` is now the documented primary control for the intelligence / latency /
cost trade-off. Hand-rolled "pick a cheaper model for easy tasks" logic is
superseded.

Effort itself does not carry across models. Opus 5.5 defaults to `medium`
(Opus 5 defaulted to `high`), and at the same level it thinks more per turn:

> "Effort level names don't correspond to the same amount of thinking across
> models: in Anthropic's testing, Claude Opus 5.5 at `medium` matches or exceeds
> Claude Opus 5 at `high` on coding and knowledge-work evaluations, …"

> "Reserve `xhigh` and `max` for work where you've measured a quality gain."

So an `effortLevel` in `settings.json`, a per-model level saved under
`modelSettings` (which takes precedence over `effortLevel` for that model), or
`CLAUDE_CODE_EFFORT_LEVEL` in its `env` (which overrides both), set to `high` or
above for Opus 5 is now a cost and latency finding.
Report it as a question — the user may have measured a reason — not as an error.

### Scaffolding for charts, diagrams and screenshots

> "Re-test whether you still need scaffolding you built for visual inputs on
> earlier models."

Opus 5.5 at its lowest effort read dense charts more accurately than Opus 5 at
its highest. Skills that exist to pre-describe screenshots, OCR a chart into a
table before the model sees it, or walk the model through reading a diagram are
candidates for question 2 in `judgment.md`. Crop/zoom tools and higher
resolution still help on the densest inputs such as technical drawings — keep
those.

### Generic "avoid the AI look" design instructions

> "… a general instruction such as 'avoid a generic AI look' mostly swaps one
> default for another. It responds well to instructions that name specific
> patterns to avoid, …"

A design skill that says only "no AI slop" or "make it distinctive" is not
removed but rewritten: name the patterns (cream background, italic accent words
in headlines, numbered "01/02/03" section labels, monospace labels, pill
buttons, …) and extend the list from what the first result actually used.

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

Audit for the inverse too: instructions that make the model re-ask for routine
steps inside an already-approved scope ("confirm before each edit", "ask before
running tests"). They produce exactly the check-ins the quote tells the model to
avoid. The best-practices sample for balancing autonomy draws the line at
reversibility:

> "You are encouraged to take local, reversible actions like editing files or
> running tests, but for actions that are hard to reverse, affect shared
> systems, or could be destructive, ask the user before proceeding."

So not every confirmation rule qualifies. Approval before external side effects,
spending, or changes to the user's own setup (this skill's ground rule 1) is a
deliberate boundary; leave it. Harness permission prompts are a separate problem
with a separate fix: point to the built-in `/fewer-permission-prompts` rather
than editing prompts.

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

### Resumed state is a claim, not evidence

The same rule applies to what a session inherits. A skill or instruction that
restores a checkpoint, progress file or saved summary and says "continue from
here" hands the model a claim about branch, files and test results that may no
longer hold. The long-horizon guidance points the other way: re-derive state
from the sources that record it.

> "Claude's latest models are extremely effective at discovering state from the
> local filesystem."

Its example start is "Review progress.txt, tests.json, and the git log" — the
notes *and* the authoritative record. Audit resume flows for that pairing: do
they check the saved state against git and the files it describes, or treat the
summary as current fact? Built-in memory does not need this rule; Claude Code's
own memory prompt already says recalled memories reflect when they were written
and that named files should be checked before use. Do not add a blanket
"re-read everything each turn"
instruction either — that is the unconditional re-check this file removes.

### Only for unattended runs: named early stops

Not for the interactive `CLAUDE.md` — the guide says to leave this out where a
person is there to answer. It belongs in skills or prompts that run headless
(`claude -p`, scheduled routines, `/loop`). Opus 5.5 writes progress updates as
it works, and some of them end the turn with text; an unattended loop reads that
as done.

> "Claude Opus 5.5 is responsive to instructions that name the specific kinds
> of early stop you want it to avoid, such as ending the turn with a summary
> that announces the next step instead of taking it. It also helps to name the
> stops you do want, for example when no work can advance without the user's
> input."

The guide's full example names four stops: a summary that announces the next
step, an offer to continue "unless you'd prefer otherwise", a list of
non-blocking decisions, and pausing because a milestone felt like a good place.
It keeps confirmation for risky or irreversible actions. The harness side: keep
open items in a checklist and cap automatic continuations at two or three.

### Only for agents across many connected apps: explore first

For skills that act across mail, docs, sheets and CRM connectors, where the rule
the task depends on often sits somewhere the request didn't mention:

> "Before taking any action, explore broadly with tool calls: list and open the
> emails, documents, spreadsheet tabs and records across the available apps that
> could be relevant to this task, including ones the task does not explicitly
> mention, and use what you find."

Only where those sources are trusted — the instruction tells the model to act on
what it finds.

---

## Rules that contradict each other

Each rule above is judged on its own. A setup can also fail between rules: two
instructions that are each reasonable, loaded into the same session, telling the
model opposite things. The model then picks one per turn, and the user sees
behaviour that no single file explains. Read `CLAUDE.md` against the skills that
load with it and look for these pairs:

1. **Finish the scope ↔ stop at each step.** "Complete the approved task without
   asking" in one place, "confirm before each change" or a skill that pauses at
   every phase in another.
2. **Confirm outward actions ↔ a skill that pushes, deploys or posts on its own.**
   `CLAUDE.md` asks for confirmation before actions others can see; a skill runs
   `git push`, opens or merges PRs, deploys or sends messages as a routine step.
   The best-practices sample lists "pushing code, commenting on PRs/issues,
   sending messages" among "operations visible to others" that warrant
   confirmation.
3. **Preserve expected behaviour ↔ make the tests pass.** A rule against changing
   requirements next to an instruction to do whatever it takes to get the suite
   green, with nothing about assertions, fixtures or excluded tests.
4. **Trust the source ↔ trust the summary.** A rule to verify against the repo
   next to a resume flow that treats a saved checkpoint or memory file as current
   fact.

Report each as one finding: both locations as `file:line`, both lines quoted,
and when each one fires. Do not pick the winner. Which rule should hold is the
user's policy, and either side may be the deliberate one.

---

## Structural rules for skills

- **SKILL.md is a router, not a manual.** Its body loads in full the moment the
  skill is invoked. Put detail in `references/` and have SKILL.md say which file
  answers which question. A 456 KB SKILL.md costs roughly 114,000 tokens per
  invocation.
- **`description:` is the routing prompt.** A skill without one is listed under
  the first line of its body, usually a heading, and rarely routes. Write what it
  does *and* when to use it, including the literal phrases a user would type.
- **Only `name` and `description` (plus `when_to_use`) reach the router.**
  Other documented keys work — `allowed-tools`, `hooks`, `model`, `effort` on
  skills; `tools`, `model`, `effort`, `maxTurns` on agents — but they control
  execution, not routing. An undocumented key such as a custom `trigger:` is
  inert; fold its content into `description`. `inventory.py` holds the documented
  key lists.
- **A custom skill shadows a built-in one of the same name.** Check for
  collisions before naming.
- **Prefer plugins to installers.** A plugin can be updated and uninstalled. An
  `install.sh` that copies files into `$HOME/.claude` leaves them there forever.
