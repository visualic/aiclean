#!/usr/bin/env python3
"""Find things that are broken or dead in a Claude Code setup: duplicate hooks,
hooks pointing at paths that no longer exist, skills that reference an MCP
server or an environment variable that is not configured, and cross-references
to skills that are no longer installed.

Everything here is a factual check with a yes/no answer. Judgment calls -- is
this skill still worth keeping? -- belong in references/judgment.md, not in a
script.

Usage:
    python3 health.py [--root ~/.claude] [--json]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ABS_PATH = re.compile(r"(/(?:Users|home)/[^\s\"';|)]+)")
# Only the unambiguous tool-name form. Matching prose like "the X MCP" picks up
# articles and pronouns ("the", "its", "their") and produces pure noise.
MCP_REF = re.compile(r"mcp__([a-zA-Z0-9_-]+?)__")
ENV_REF = re.compile(r"\$\{?([A-Z][A-Z0-9_]{3,})\}?")

# Directories under skills/ that the harness manages itself (claude.ai skill
# sync). Their contents are not the user's to fix.
HARNESS_DIRS = {"synced"}

# Shell and runtime variables that are never user secrets.
ENV_IGNORE = {
    "PATH", "HOME", "PWD", "OLDPWD", "SHELL", "USER", "LOGNAME", "LANG", "TERM",
    "TMPDIR", "EDITOR", "PAGER", "OSTYPE", "HOSTNAME", "RANDOM", "SECONDS",
    "IFS", "UID", "GID", "PS1", "PS2", "REPLY", "FUNCNAME", "LINENO",
    "NODE_ENV", "CI", "DEBUG", "FORCE_COLOR", "NO_COLOR", "SYSTEMROOT",
}

# Credentials a CLI can take from its own login file instead of the
# environment. The Codex CLI accepts CODEX_API_KEY, OPENAI_API_KEY, or a
# `codex login` session in $CODEX_HOME/auth.json. The second field limits the
# exemption to skills that are about that CLI, so an unrelated skill that needs
# OPENAI_API_KEY is still flagged.
def _codex_login() -> str:
    return os.path.join(os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex"),
                        "auth.json")


LOGIN_FILES = {
    "CODEX_API_KEY": (_codex_login, "codex"),
    "OPENAI_API_KEY": (_codex_login, "codex"),
}


def covered_by_login(var: str, text: str) -> bool:
    entry = LOGIN_FILES.get(var)
    if not entry:
        return False
    path_fn, topic = entry
    return topic in text.lower() and os.path.isfile(path_fn())


def load_settings(root: str) -> list[tuple[str, dict]]:
    out = []
    for name in ("settings.json", "settings.local.json"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            try:
                out.append((name, json.load(open(p, encoding="utf-8"))))
            except json.JSONDecodeError as exc:
                out.append((name, {"__parse_error__": str(exc)}))
    return out


def check_hooks(root: str) -> dict:
    dupes, dead, total, parse_errors = [], [], 0, []
    for fname, data in load_settings(root):
        if "__parse_error__" in data:
            parse_errors.append((fname, data["__parse_error__"]))
            continue
        seen = collections.Counter()
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                matcher = group.get("matcher", "")
                for hook in group.get("hooks", []):
                    cmd = hook.get("command", "")
                    total += 1
                    key = (event, matcher, cmd)
                    seen[key] += 1
                    if seen[key] > 1:
                        dupes.append((fname, event, matcher, cmd[:90]))
                    for path in ABS_PATH.findall(cmd):
                        if not os.path.exists(path):
                            dead.append((fname, event, path))
    return {"total": total, "duplicates": dupes, "dead_paths": dead,
            "parse_errors": parse_errors}


def configured_mcp_servers() -> set[str]:
    servers: set[str] = set()
    for p in (os.path.expanduser("~/.claude.json"),
              os.path.expanduser("~/.claude/settings.json"),
              os.path.expanduser("~/.claude/settings.local.json")):
        if not os.path.exists(p):
            continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        servers |= set(data.get("mcpServers") or {})
        for proj in (data.get("projects") or {}).values():
            if isinstance(proj, dict):
                servers |= set(proj.get("mcpServers") or {})
    return {s.lower() for s in servers}


def check_dependencies(root: str) -> dict:
    """Skills that name an MCP server or an env var that is not available."""
    servers = configured_mcp_servers()
    env_present = set(os.environ)
    missing_mcp, missing_env = [], []

    for skill_md in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")):
        sid = os.path.basename(os.path.dirname(skill_md))
        try:
            text = open(skill_md, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue

        named = {s.lower() for s in MCP_REF.findall(text)}
        for server in sorted(named):
            if server and server not in servers and \
                    not any(server in s for s in servers):
                missing_mcp.append((sid, server))

        wanted = {v for v in ENV_REF.findall(text)
                  if v not in ENV_IGNORE and not v.startswith("CLAUDE_")}
        # Only flag things that look like credentials; deploy configs are
        # legitimately supplied per-project at run time.
        creds = {v for v in wanted
                 if v.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))}
        for var in sorted(creds - env_present):
            if not covered_by_login(var, text):
                missing_env.append((sid, var))

    return {"missing_mcp": missing_mcp, "missing_env": missing_env,
            "configured_mcp": sorted(servers)}


def check_references(root: str) -> list[tuple[str, str, str]]:
    """Files under skills/ and agents/ that point at a skill that is gone."""
    installed = {os.path.basename(os.path.dirname(p))
                 for p in glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))}
    broken = []
    patterns = [
        (re.compile(r"skills/([a-zA-Z0-9_-]+)/"), "path"),
        (re.compile(r'skill:\s*"([a-zA-Z0-9_-]+)"'), "Skill() call"),
    ]
    roots = [os.path.join(root, "skills"), os.path.join(root, "agents"),
             os.path.join(root, "commands")]
    for base in roots:
        for path in glob.glob(os.path.join(base, "**", "*.md"), recursive=True):
            owner = os.path.relpath(path, root).split(os.sep)[1] \
                if os.sep in os.path.relpath(path, root) else ""
            if base.endswith(os.sep + "skills") and owner in HARNESS_DIRS:
                continue
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for rx, kind in patterns:
                for name in set(rx.findall(text)):
                    if name != owner and name not in installed:
                        broken.append((os.path.relpath(path, root), name, kind))
    return sorted(set(broken))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.expanduser(args.root)
    hooks = check_hooks(root)
    deps = check_dependencies(root)
    refs = check_references(root)

    if args.json:
        print(json.dumps({"hooks": hooks, "dependencies": deps,
                          "broken_references": refs},
                         ensure_ascii=False, indent=2))
        return 0

    print(f"root: {root}\n")

    print(f"[hooks] {hooks['total']} registered")
    for fname, err in hooks["parse_errors"]:
        print(f"  INVALID JSON  {fname}: {err}")
    if hooks["duplicates"]:
        print(f"  duplicates: {len(hooks['duplicates'])} "
              f"(each fires once per copy)")
        for fname, event, matcher, cmd in hooks["duplicates"]:
            print(f"    {fname}  {event}  {matcher[:32]}  {cmd}")
    else:
        print("  duplicates: 0")
    if hooks["dead_paths"]:
        print(f"  dead paths: {len(hooks['dead_paths'])}")
        for fname, event, path in hooks["dead_paths"]:
            print(f"    {fname}  {event}  {path}")
    else:
        print("  dead paths: 0")

    print(f"\n[dependencies]")
    print(f"  configured MCP servers: {', '.join(deps['configured_mcp']) or '(none)'}")
    if deps["missing_mcp"]:
        print("  skills naming an MCP server that is not in any settings file:")
        print("    (harness-provided servers -- conductor, claude-in-chrome and")
        print("     similar -- are injected at runtime and never appear here.")
        print("     Confirm a server is genuinely absent before acting.)")
        for sid, server in deps["missing_mcp"]:
            print(f"    {sid:<28} -> {server}")
    if deps["missing_env"]:
        print(f"  skills naming a credential that is not set:")
        for sid, var in deps["missing_env"]:
            print(f"    {sid:<28} -> {var}")
    if not deps["missing_mcp"] and not deps["missing_env"]:
        print("  no missing MCP servers or credentials")

    print(f"\n[broken references] {len(refs)}")
    for path, name, kind in refs:
        print(f"  {path}  ->  {name}  ({kind})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
