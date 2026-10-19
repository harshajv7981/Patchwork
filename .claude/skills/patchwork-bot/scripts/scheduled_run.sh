#!/bin/zsh
# Unattended run of /patchwork-bot, launched daily by launchd (see SKILL.md "Scheduling").
#   scheduled_run.sh [run|watch|status]      default: run
# Logs go to ~/.patchwork-bot/logs/; the last 60 are kept.
set -u
# launchd starts with a minimal PATH; gh, docker and claude live in Homebrew.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PW="$(cd "$(dirname "$0")/../../../.." && pwd)"
LOG_DIR="$HOME/.patchwork-bot/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"
CMD="${1:-run}"

cd "$PW" || exit 1
{
  echo "== patchwork-bot $CMD @ $(date) =="
  # Unattended, so tools must be pre-approved. Bash covers gh/git/docker/python; the
  # bot's own limits (state.py) are what bound what it can post.
  claude -p "/patchwork-bot $CMD" \
    --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" "Agent" \
    --add-dir "$HOME/.patchwork-bot" --add-dir "${TMPDIR:-/tmp}"
  echo "== exit=$? @ $(date) =="
} > "$LOG" 2>&1

ls -1t "$LOG_DIR"/run-*.log 2>/dev/null | tail -n +61 | xargs rm -f 2>/dev/null
exit 0
