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
A skill with no `description:` frontmatter is invisible to the router, so it
*could not* have been invoked. Cross-check zero counts against inventory.py
before concluding a skill is unwanted. See references/judgment.md.

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
# user-typed slash commands, e.g. {"role":"user","content":"/foo ..."}
SLASH = re.compile(r'"(?:text|content)"\s*:\s*"/([a-zA-Z0-9:_-]{2,})')

# Slash-looking strings that are just file paths, not commands.
PATH_NOISE = {"tmp", "opt", "usr", "var", "bin", "etc", "private", "home",
              "users", "dev", "app", "api", "v1", "v2", "src", "docs"}


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
                    if '"/' in line:
                        for s in SLASH.findall(line):
                            if s.lower() not in PATH_NOISE:
                                slashes[s] += 1
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
        print("  description could not have been invoked, so its zero means")
        print("  nothing. See references/judgment.md.")
        for name in never:
            print(f"  {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
