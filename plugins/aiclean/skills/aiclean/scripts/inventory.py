#!/usr/bin/env python3
"""Inventory every skill and agent visible to Claude Code, and measure what the
routing text costs at session start.

Only the `name` + `description` frontmatter of each skill and agent is loaded
into the system prompt on every new session. SKILL.md bodies are read only when
a skill is actually invoked -- which is why an oversized SKILL.md is a bomb that
goes off on use, while a bloated description is a tax paid on every session.

Usage:
    python3 inventory.py [--root ~/.claude] [--json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import sys

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
# a description ends at the next top-level YAML key, or at the end of the block
DESCRIPTION = re.compile(r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", re.S | re.M)
NAME = re.compile(r"^name:\s*(.*)$", re.M)

# SKILL.md should be a router. Anthropic's guidance is to keep it small and put
# detail in references/. These thresholds are where it starts to hurt.
BODY_WARN = 10_000      # bytes
BODY_CRITICAL = 40_000  # bytes

# Frontmatter keys Claude Code documents for skills and for subagents
# (code.claude.com/docs/en/skills, /sub-agents). Anything else is inert -- most
# commonly a hand-rolled `trigger:` key whose content the router never sees.
SKILL_KEYS = {"name", "description", "when_to_use", "argument-hint", "arguments",
              "disable-model-invocation", "user-invocable", "allowed-tools",
              "disallowed-tools", "model", "effort", "context", "agent",
              "background", "hooks", "paths", "shell", "metadata", "license",
              "compatibility"}
AGENT_KEYS = {"name", "description", "tools", "disallowedTools", "model",
              "permissionMode", "maxTurns", "skills", "mcpServers", "hooks",
              "memory", "background", "omitClaudeMd", "effort", "isolation",
              "color", "initialPrompt", "experimental"}

# Directories under skills/ that the harness manages itself (claude.ai skill
# sync). They are not user skills and have no top-level SKILL.md by design.
HARNESS_DIRS = {"synced"}


def parse(path: str, known: set[str], fallback: bool = True) -> dict:
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return {}
    m = FRONTMATTER.match(text)
    if not m:
        return {"frontmatter": False, "body_bytes": len(text.encode()),
                "fallback": first_line(text) if fallback else None}
    block = m.group(1)
    desc = DESCRIPTION.search(block)
    name = NAME.search(block)
    keys = set(re.findall(r"^([a-zA-Z_-]+):", block, re.M))
    return {
        "frontmatter": True,
        "name": name.group(1).strip() if name else None,
        "description": " ".join(desc.group(1).split()) if desc else None,
        "fallback": None if desc or not fallback else first_line(text[m.end():]),
        "extra_keys": sorted(keys - known),
        "body_bytes": len(text[m.end():].encode()),
        "total_bytes": len(text.encode()),
    }


def first_line(body: str) -> str:
    # With no description, Claude Code lists the skill under the first non-empty
    # line of the body (code.claude.com/docs/en/skills) -- usually a heading.
    for line in body.splitlines():
        if line.strip():
            return line.strip()
    return ""


def birth(path: str) -> str:
    try:
        st = os.stat(path)
        ts = getattr(st, "st_birthtime", st.st_mtime)
        return _dt.date.fromtimestamp(ts).isoformat()
    except OSError:
        return "?"


def collect(root: str) -> dict:
    items = {"skills": [], "agents": []}

    for skill_md in sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))):
        d = os.path.dirname(skill_md)
        info = parse(skill_md, SKILL_KEYS)
        info["id"] = os.path.basename(d)
        info["path"] = skill_md
        info["created"] = birth(d)
        info["has_references"] = os.path.isdir(os.path.join(d, "references")) or \
            os.path.isdir(os.path.join(d, "reference"))
        items["skills"].append(info)

    # a skill directory with no SKILL.md is not a skill: nothing lists it
    for d in sorted(glob.glob(os.path.join(root, "skills", "*"))):
        if os.path.basename(d) in HARNESS_DIRS:
            continue
        if os.path.isdir(d) and not os.path.exists(os.path.join(d, "SKILL.md")):
            items["skills"].append({"id": os.path.basename(d), "path": d,
                                    "frontmatter": False, "no_skill_md": True,
                                    "created": birth(d), "body_bytes": 0})

    for agent_md in sorted(glob.glob(os.path.join(root, "agents", "*.md"))):
        # `description` is required for agents; there is no first-line fallback
        info = parse(agent_md, AGENT_KEYS, fallback=False)
        info["id"] = os.path.basename(agent_md)[:-3]
        info["path"] = agent_md
        info["created"] = birth(agent_md)
        items["agents"].append(info)

    return items


def routing_cost(items: dict) -> dict:
    chars = 0
    for group in items.values():
        for it in group:
            chars += len(it.get("description") or it.get("fallback") or "")
    # Korean/English mixed prose runs roughly 3 characters per token.
    return {"chars": chars, "approx_tokens": chars // 3}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.expanduser(args.root)
    if not os.path.isdir(root):
        print(f"not found: {root}", file=sys.stderr)
        return 1

    items = collect(root)
    cost = routing_cost(items)

    if args.json:
        print(json.dumps({"root": root, "items": items, "routing": cost},
                         ensure_ascii=False, indent=2))
        return 0

    skills, agents = items["skills"], items["agents"]
    print(f"root: {root}")
    print(f"skills: {len(skills)}   agents: {len(agents)}")
    print(f"routing text loaded every session: {cost['chars']:,} chars "
          f"(~{cost['approx_tokens']:,} tokens)")

    dead = [s for s in skills if s.get("no_skill_md")]
    if dead:
        print(f"\n[no SKILL.md] {len(dead)} -- not a skill, cannot be invoked:")
        for s in dead:
            print(f"  {s['id']}")

    missing = [s for s in skills if not s.get("description") and not s.get("no_skill_md")]
    if missing:
        print(f"\n[no description] {len(missing)} -- the router sees only the first "
              f"line of the body; a bare heading barely routes:")
        for s in missing:
            why = "no frontmatter" if not s.get("frontmatter") else "no description: key"
            print(f"  {s['id']:<32} ({why}) routes on: {s.get('fallback') or '(empty)'!r}")

    big = sorted([s for s in skills if s.get("body_bytes", 0) > BODY_WARN],
                 key=lambda s: -s["body_bytes"])
    if big:
        worst = sum(s["body_bytes"] for s in big[:1])
        print(f"\n[oversized SKILL.md] {len(big)} over {BODY_WARN:,} B -- the body "
              f"loads in full on every invocation; move detail to references/.")
        print(f"  largest single invocation cost: ~{worst//4:,} tokens")
        for s in big[:15]:
            flag = "CRITICAL" if s["body_bytes"] > BODY_CRITICAL else "warn"
            ref = "" if s.get("has_references") else "  (no references/ dir)"
            print(f"  {flag:<8} {s['id']:<32} {s['body_bytes']:>9,} B "
                  f"(~{s['body_bytes']//4:,} tokens){ref}")
        if len(big) > 15:
            print(f"  ... and {len(big)-15} more (use --json for the full list)")

    extra = [s for s in skills + agents if s.get("extra_keys")]
    if extra:
        print(f"\n[inert frontmatter keys] {len(extra)} -- not documented Claude "
              f"Code keys; if the router should see it, move it into description:")
        for s in extra:
            print(f"  {s['id']:<32} {', '.join(s['extra_keys'])}")

    print("\n[all skills by age]")
    for s in sorted(skills, key=lambda s: s.get("created", "?")):
        d = (s.get("description") or "")[:60]
        print(f"  {s.get('created','?')}  {s['id']:<32} {s.get('body_bytes',0):>8,} B  {d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
