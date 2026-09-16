#!/bin/sh
# Install the aiclean skill for harnesses that do not support Claude Code
# plugins — Codex CLI and friends.
#
# Claude Code users do NOT need this script. Use the plugin instead:
#     /plugin marketplace add visualic/aiclean
#     /plugin install aiclean@visualic
#
# This links (does not copy) the skill from this checkout, so `git pull` updates
# every harness at once. Uninstall with: ./install.sh --uninstall
#
# Usage:
#   ./install.sh                 detect harnesses and link into each
#   ./install.sh --harness codex link into ~/.codex only
#   ./install.sh --uninstall     remove the links
#   ./install.sh --list          show what would be touched

set -eu

SKILL_NAME="aiclean"
SRC="$(cd "$(dirname "$0")" && pwd)/plugins/aiclean/skills/$SKILL_NAME"

# Harness home directories that read ~/<dir>/skills/<name>/SKILL.md.
# .claude is intentionally absent: Claude Code should install the plugin.
HARNESSES=".codex .agents .cursor .gemini .hermes"

MODE="install"
ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) MODE="uninstall"; shift ;;
    --list)      MODE="list"; shift ;;
    --harness)   ONLY="${2:-}"; [ -z "$ONLY" ] && { echo "--harness needs a value" >&2; exit 1; }; shift 2 ;;
    --harness=*) ONLY="${1#--harness=}"; shift ;;
    -h|--help)   sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)           echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

if [ ! -d "$SRC" ]; then
  echo "skill not found at $SRC" >&2
  echo "run this script from inside the repository checkout." >&2
  exit 1
fi

if [ -n "$ONLY" ]; then
  case "$ONLY" in
    .*) HARNESSES="$ONLY" ;;
    *)  HARNESSES=".$ONLY" ;;
  esac
fi

found=0
for h in $HARNESSES; do
  home="$HOME/$h"
  # Only touch a harness the user actually has.
  [ -d "$home" ] || continue
  found=$((found + 1))
  dest_dir="$home/skills"
  dest="$dest_dir/$SKILL_NAME"

  case "$MODE" in
    list)
      status="(absent)"
      [ -L "$dest" ] && status="linked -> $(readlink "$dest")"
      [ -d "$dest" ] && [ ! -L "$dest" ] && status="(a real directory is in the way)"
      printf '  %-12s %s  %s\n' "$h" "$dest" "$status"
      ;;
    uninstall)
      if [ -L "$dest" ]; then
        rm "$dest"
        echo "  removed link  $dest"
      elif [ -d "$dest" ]; then
        echo "  SKIPPED       $dest is a real directory, not our link — remove it yourself" >&2
      fi
      ;;
    install)
      mkdir -p "$dest_dir"
      if [ -d "$dest" ] && [ ! -L "$dest" ]; then
        echo "  SKIPPED       $dest already exists and is not a link" >&2
        continue
      fi
      ln -snf "$SRC" "$dest"
      echo "  linked        $dest -> $SRC"
      ;;
  esac
done

if [ "$found" -eq 0 ]; then
  echo "No supported harness directory found under \$HOME (looked for: $HARNESSES)."
  echo "If you use Claude Code, install the plugin instead:"
  echo "  /plugin marketplace add visualic/aiclean"
  exit 0
fi

[ "$MODE" = "install" ] && cat <<'EOF'

Done. Open a new session in your agent and ask it to audit your Claude setup,
or run the skill by name: aiclean

Claude Code users: use the plugin instead of this script —
  /plugin marketplace add visualic/aiclean
  /plugin install aiclean@visualic
EOF

exit 0
