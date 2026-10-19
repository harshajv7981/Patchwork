#!/bin/zsh

export ANTHROPIC_BASE_URL="http://localhost:20128/v1"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="antigravity/claude-sonnet-4-6"
export ANTHROPIC_SMALL_FAST_MODEL="antigravity/claude-sonnet-4-6"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

claude "$@"
