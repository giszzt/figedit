#!/usr/bin/env python3
"""Load image-backend API keys from the skill-root `.env` file.

Real environment variables always win; the file only fills in what is not
already set (standard dotenv semantics). Supported keys are listed in
`env.example` at the skill root. Never commit `.env` — it is gitignored.
"""
from __future__ import annotations

import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent


def load() -> list[str]:
    """Merge skill-root .env into os.environ. Returns the keys that were
    actually loaded from the file (for diagnostics)."""
    env_file = SKILL_ROOT / ".env"
    loaded: list[str] = []
    if not env_file.exists():
        return loaded
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


if __name__ == "__main__":
    print({"loaded_from_env_file": load()})
