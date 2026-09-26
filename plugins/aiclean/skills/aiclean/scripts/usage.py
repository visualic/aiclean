#!/usr/bin/env python3
"""Count how often each skill and subagent was actually invoked, by reading the
session transcripts in ~/.claude/projects.

THE TRAP THIS SCRIPT EXISTS TO AVOID
------------------------------------
Every session's system prompt contains the full list of available skills. So a
plain `grep -rl "<skill-name>" *.jsonl` matches essentially every transcript and
reports the same count for every skill -- including skills that have never been
run. That number looks like evidence and is worthless.

Real invocations appear as tool_use blocks:
    {"name":"Skill","input":{"skill":"<name>", ...}}
    {"name":"Task","input":{"subagent_type":"<name>", ...}}

This script counts only those.

A ZERO IS NOT ALWAYS EVIDENCE
-----------------------------
A skill with no `description:` frontmatter is listed under the first line of its
body. When that line is a bare heading, the skill barely routes and its zero is
weak evidence.
Cross-check zero counts against inventory.py first. See references/judgment.md.

Usage:
    python3 usage.py [--root ~/.claude] [--json]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

SKILL_CALL = re.compile(r'"name"\s*:\s*"Skill"\s*,\s*"input"\s*:\s*\{[^}]*?"skill"\s*:\s*"([^"]+)"')
AGENT_CALL = re.compile(r'"subagent_type"\s*:\s*"([^"]+)"')
# User-typed slash commands live in user messages whose content is a plain
# string: either tagged, <command-name>/foo</command-name> (after a
# <command-message> tag when the command runs a skill), or as typed, "/foo args"
# (how some hosts, Conductor among them, send it). Anything else that starts
# with "/" -- tool output, file paths, URL routes like /products/vn -- is not a
# command, so the message is parsed rather than grepped.
COMMAND_TAG = re.compile(r"<command-name>/([a-zA-Z0-9:_-]+)</command-name>")
TYPED_COMMAND = re.compile(r"/([a-zA-Z0-9:_-]+)(?=\s|$)")


def typed_command(line: str) -> str | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    msg = entry.get("message") if isinstance(entry, dict) else None
    if entry.get("type") != "user" or not isinstance(msg, dict) \
            or msg.get("role") != "user" or not isinstance(msg.get("content"), str):
        return None
    content = msg["content"].lstrip()
    tag = COMMAND_TAG.search(content[:300])
    if tag and content.startswith(("<command-name>", "<command-message>")):
        return tag.group(1)
    typed = TYPED_COMMAND.match(content)
    return typed.group(1) if typed else None


def toolkit_prefixes(names: set[str], minimum: int = 5) -> set[str]:
    """Prefixes like `gstack` that a toolkit puts on many skill names at once."""
    counts = collections.Counter(n.split("-", 1)[0] for n in names if "-" in n)
    return {p for p, c in counts.items() if c >= minimum}


def base_name(name: str, prefixes: set[str]) -> str:
    head, _, rest = name.partition("-")
    return rest if rest and head in prefixes else name


def never_invoked(root: str, res: dict) -> tuple[list[str], dict[str, list[str]]]:
    """Installed skills with no recorded use, and ones used only under another name.

    Toolkits can rename every skill at once (gstack's skill_prefix turns
    `codex` into `gstack-codex`). Transcripts keep the old name, so a strict
    match would call a skill used last week "never invoked".
    """
    installed = {os.path.basename(os.path.dirname(p))
                 for p in glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))}
    used = set(res["skills"]) | set(res["slash"])
    prefixes = toolkit_prefixes(installed)
    by_base: dict[str, set[str]] = collections.defaultdict(set)
    for u in used:
        by_base[base_name(u, prefixes)].add(u)
    never, renamed = [], {}
    for name in sorted(installed - used):
        earlier = sorted(by_base.get(base_name(name, prefixes), set()) - {name})
        if earlier:
            renamed[name] = earlier
        else:
            never.append(name)
    return never, renamed


# Other harness homes that link skills in from ~/.claude (install.sh, gstack's
# setup --host codex, ...). Their usage is not in Claude's transcripts.
OTHER_HOMES = ["~/.codex", "~/.agents", "~/.cursor", "~/.gemini", "~/.hermes",
               "~/.factory", "~/.kiro", "~/.config/opencode"]


def shared_with_other_tools(root: str) -> dict[str, list[str]]:
    """Installed skills that another tool's home links into.

    A skill counts when its directory, or the directory its SKILL.md resolves
    into (a toolkit install such as ~/.claude/skills/gstack), is the target of
    a symlink under another home's skills/ tree.
    """
    skills_dir = os.path.realpath(os.path.join(root, "skills"))
    linked: dict[str, set[str]] = collections.defaultdict(set)
    for home in OTHER_HOMES:
        base = os.path.expanduser(home)
        tree = os.path.join(base, "skills")
        if not os.path.isdir(tree) or os.path.realpath(base) == os.path.realpath(root):
            continue
        for cur, dirs, files in os.walk(tree):
            if cur[len(tree):].count(os.sep) >= 3:
                dirs[:] = []
            for entry in dirs + files:
                path = os.path.join(cur, entry)
                if not os.path.islink(path):
                    continue
                target = os.path.realpath(path)
                if target.startswith(skills_dir + os.sep):
                    top = os.path.relpath(target, skills_dir).split(os.sep)[0]
                    linked[top].add(home)
    shared: dict[str, list[str]] = {}
    for skill_md in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")):
        name = os.path.basename(os.path.dirname(skill_md))
        homes = set(linked.get(name, ()))
        real = os.path.realpath(skill_md)
        if real.startswith(skills_dir + os.sep):
            homes |= linked.get(os.path.relpath(real, skills_dir).split(os.sep)[0], set())
        if homes:
            shared[name] = sorted(homes)
    return dict(sorted(shared.items()))


def scan(root: str) -> dict:
    skills = collections.Counter()
    agents = collections.Counter()
    slashes = collections.Counter()
    files = sorted(glob.glob(os.path.join(root, "projects", "**", "*.jsonl"),
                             recursive=True))
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if '"Skill"' in line:
                        skills.update(SKILL_CALL.findall(line))
                    if "subagent_type" in line:
                        agents.update(AGENT_CALL.findall(line))
                    if '"/' in line or "<command-" in line:
                        name = typed_command(line)
                        if name:
                            slashes[name] += 1
        except OSError:
            continue
    return {"sessions": len(files), "skills": skills,
            "agents": agents, "slash": slashes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.expanduser(args.root)
    if not os.path.isdir(os.path.join(root, "projects")):
        print(f"no transcripts under {root}/projects", file=sys.stderr)
        return 1

    res = scan(root)

    if args.json:
        out = {k: (dict(v) if isinstance(v, collections.Counter) else v)
               for k, v in res.items()}
        out["never_invoked"], out["used_under_other_name"] = never_invoked(root, res)
        out["shared_with_other_tools"] = shared_with_other_tools(root)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print(f"scanned {res['sessions']} session transcripts under {root}/projects\n")

    print("[Skill tool invocations]")
    if res["skills"]:
        for name, n in res["skills"].most_common():
            print(f"  {n:>5}  {name}")
    else:
        print("  (none)")

    print("\n[subagent invocations]")
    if res["agents"]:
        for name, n in res["agents"].most_common(25):
            print(f"  {n:>5}  {name}")
    else:
        print("  (none)")

    print("\n[user-typed slash commands]")
    for name, n in res["slash"].most_common(20):
        print(f"  {n:>5}  /{name}")

    # Installed but never invoked. Report it as a question, not a verdict.
    installed = glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))
    never, renamed = never_invoked(root, res)
    if renamed:
        print(f"\n[used under another name] {len(renamed)} -- history is recorded "
              f"under the name the skill had then:")
        for name, earlier in renamed.items():
            print(f"  {name:<32} as {', '.join(earlier)}")
    shared = shared_with_other_tools(root)
    if shared:
        by_home: dict[str, list[str]] = collections.defaultdict(list)
        for name, homes in shared.items():
            for h in homes:
                by_home[h].append(name)
        print(f"\n[shared with another tool] {len(shared)} -- another tool links into "
              f"these; its use is not in these transcripts, and archiving them "
              f"breaks it:")
        for h, names in sorted(by_home.items()):
            more = f" ... (+{len(names) - 8})" if len(names) > 8 else ""
            print(f"  {h:<20} {', '.join(names[:8])}{more}")
    if never:
        print(f"\n[installed but never invoked] {len(never)} of {len(installed)}")
        print("  Check each against inventory.py first: a skill with no")
        print("  description routes on the first line of its body, and if that")
        print("  line is a bare heading its zero is weak evidence. A skill marked")
        print("  shared may be in daily use elsewhere. See references/judgment.md.")
        for name in never:
            mark = f"  (shared: {', '.join(shared[name])})" if name in shared else ""
            print(f"  {name}{mark}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
