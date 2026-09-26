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
        print(json.dumps({k: (dict(v) if isinstance(v, collections.Counter) else v)
                          for k, v in res.items()}, ensure_ascii=False, indent=2))
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
    installed = {os.path.basename(os.path.dirname(p))
                 for p in glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))}
    never = sorted(installed - set(res["skills"]) - set(res["slash"]))
    if never:
        print(f"\n[installed but never invoked] {len(never)} of {len(installed)}")
        print("  Check each against inventory.py first: a skill with no")
        print("  description routes on the first line of its body, and if that")
        print("  line is a bare heading its zero is weak evidence.")
        print("  See references/judgment.md.")
        for name in never:
            print(f"  {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
