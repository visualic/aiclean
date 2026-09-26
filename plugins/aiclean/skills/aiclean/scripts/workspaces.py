#!/usr/bin/env python3
"""Find project-level .claude/ directories and compare them against the
user-level setup.

Why this matters more than it looks: a project-level `.claude/skills/` is
committed configuration. It loads alongside the global setup for anyone working
in that repo, it is usually a snapshot of whatever a toolkit's installer copied
in on the day it ran, and it goes stale silently while the global copy gets
updated. On a name clash the two kinds resolve in opposite directions
(code.claude.com/docs/en/skills, /sub-agents): the personal skill runs over the
project skill, but the project agent runs over the personal agent.

Teams working in git worktrees -- Conductor workspaces, `git worktree add`,
anything that gives each task its own checkout -- hit this hardest: every
worktree of the same repo carries its own copy, so one stale commit multiplies
across dozens of directories.

This script only reports. Changing a repository's committed configuration
affects everyone else working in it, so raise it with the user rather than
editing it.

Usage:
    python3 workspaces.py [--root ~/conductor/workspaces] [--root ~/projects] [--json]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

DEFAULT_ROOTS = [
    "~/conductor/workspaces",
    "~/AI",
    "~/projects",
    "~/src",
    "~/dev",
]


def global_skills() -> set[str]:
    root = os.path.expanduser("~/.claude/skills")
    return {os.path.basename(os.path.dirname(p))
            for p in glob.glob(os.path.join(root, "*", "SKILL.md"))}


def agent_name(path: str) -> str:
    # An agent is identified by its frontmatter `name`, not its file name
    # (code.claude.com/docs/en/sub-agents). Fall back to the file name.
    try:
        text = open(path, encoding="utf-8", errors="ignore").read(4096)
    except OSError:
        text = ""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        n = re.search(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", m.group(1), re.M)
        if n:
            return n.group(1)
    return os.path.basename(path)[:-3]


def agent_names(agents_dir: str) -> list[str]:
    # agents/ is scanned recursively; subfolders do not change identity
    return sorted({agent_name(p) for p in
                   glob.glob(os.path.join(agents_dir, "**", "*.md"), recursive=True)})


def global_agents() -> set[str]:
    return set(agent_names(os.path.expanduser("~/.claude/agents")))


def scan(roots: list[str], max_depth: int = 3) -> list[dict]:
    found = []
    seen = set()
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            continue
        # look for <root>/*/.claude, <root>/*/*/.claude, <root>/*/*/*/.claude
        for depth in range(1, max_depth + 1):
            pattern = os.path.join(root, *(["*"] * depth), ".claude")
            for cdir in glob.glob(pattern):
                if not os.path.isdir(cdir) or cdir in seen:
                    continue
                seen.add(cdir)
                project = os.path.dirname(cdir)
                skills = sorted(
                    os.path.basename(os.path.dirname(p))
                    for p in glob.glob(os.path.join(cdir, "skills", "*", "SKILL.md")))
                agents = agent_names(os.path.join(cdir, "agents"))
                has_settings = any(
                    os.path.exists(os.path.join(cdir, n))
                    for n in ("settings.json", "settings.local.json"))
                if not (skills or agents or has_settings):
                    continue
                found.append({
                    "project": project,
                    "display": project.replace(os.path.expanduser("~"), "~"),
                    "skills": skills,
                    "agents": agents,
                    "settings": has_settings,
                })
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None,
                    help="directory to scan (repeatable). Defaults cover common layouts.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    roots = args.root or DEFAULT_ROOTS
    found = scan(roots)
    gskills = global_skills()
    gagents = global_agents()
    for item in found:
        item["skills_shadowed_by_global"] = sorted(set(item["skills"]) & gskills)
        item["agents_overriding_global"] = sorted(set(item["agents"]) & gagents)

    if args.json:
        print(json.dumps({"roots": roots, "global_skills": sorted(gskills),
                          "global_agents": sorted(gagents),
                          "projects": found}, ensure_ascii=False, indent=2))
        return 0

    if not found:
        print(f"no project-level .claude/ found under: {', '.join(roots)}")
        return 0

    print(f"scanned: {', '.join(roots)}")
    print(f"projects carrying their own .claude/: {len(found)}\n")

    # Group identical skill sets: worktrees of one repo share a commit, so they
    # report as one finding rather than twenty.
    groups = collections.defaultdict(list)
    for item in found:
        groups[tuple(item["skills"])].append(item)

    for skills, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if not skills:
            continue
        overlap = sorted(set(skills) & gskills)
        print(f"[{len(skills)} skills x {len(items)} director{'y' if len(items)==1 else 'ies'}]")
        for it in items[:4]:
            print(f"    {it['display']}")
        if len(items) > 4:
            print(f"    ... and {len(items)-4} more")
        print(f"    skills: {', '.join(skills[:10])}"
              f"{' ...' if len(skills) > 10 else ''}")
        if overlap:
            print(f"    ALSO INSTALLED GLOBALLY: {len(overlap)} of these "
                  f"({', '.join(overlap[:6])}{' ...' if len(overlap) > 6 else ''})")
            print(f"    -> the global copy runs; these project copies are shadowed.")
            print(f"       Edits to them do nothing in these directories.")
        only_project = len(skills) - len(overlap)
        if only_project:
            print(f"    -> {only_project} project-only skill(s) add to the routing list here.")
        print()

    agent_items = [i for i in found if i["agents"]]
    if agent_items:
        print("[project-level agents]")
        for it in agent_items[:12]:
            print(f"    {it['display']}: {', '.join(it['agents'][:8])}"
                  f"{' ...' if len(it['agents']) > 8 else ''}")
            clash = it["agents_overriding_global"]
            if clash:
                print(f"      overrides global: {', '.join(clash)} -- the project copy "
                      f"runs here, and it is usually the older one")
        if len(agent_items) > 12:
            print(f"    ... and {len(agent_items)-12} more")
        print("    These are often hand-written domain agents, not toolkit")
        print("    leftovers. Read before suggesting anything.\n")

    print("This script reports only. A project's .claude/ is committed")
    print("configuration -- changing it affects everyone working in that repo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
