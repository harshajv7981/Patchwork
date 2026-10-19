"""Small task-aware model router with environment-configurable fallbacks."""

from __future__ import annotations

import os

# provider -> (env prefix, built-in default model)
_PROVIDERS = {
    "openrouter": ("OPENROUTER", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    "groq": ("GROQ", "openai/gpt-oss-120b"),
    "gemini": ("GEMINI", "gemini-2.5-flash"),
    "ollama": ("OLLAMA", "qwen3.5:9b"),
}


def provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def model_for(task: str) -> str:
    """<PREFIX>_<TASK>_MODEL, else <PREFIX>_MODEL, else the provider default. Unknown tasks use coding."""
    prefix, fallback = _PROVIDERS.get(provider_name(), _PROVIDERS["ollama"])
    task = task if task in {"triage", "coding", "review"} else "coding"
    return os.getenv(f"{prefix}_{task.upper()}_MODEL", os.getenv(f"{prefix}_MODEL", fallback))
