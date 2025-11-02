from __future__ import annotations

import os
from pathlib import Path

APP_ID = "ai-app"  # keep stable; use the distribution name

HOME = Path.home()
XDG_CONFIG_HOME = Path(os.getenv("XDG_CONFIG_HOME", HOME / ".config"))
XDG_DATA_HOME = Path(os.getenv("XDG_DATA_HOME", HOME / ".local" / "share"))
XDG_CACHE_HOME = Path(os.getenv("XDG_CACHE_HOME", HOME / ".cache"))
XDG_STATE_HOME = Path(os.getenv("XDG_STATE_HOME", HOME / ".local" / "state"))

# Allow per-category overrides (stronger than XDG)
AI_APP_CONFIG_DIR = Path(os.getenv("AI_APP_CONFIG_DIR", XDG_CONFIG_HOME / APP_ID))
AI_APP_DATA_DIR = Path(os.getenv("AI_APP_DATA_DIR", XDG_DATA_HOME / APP_ID))
AI_APP_CACHE_DIR = Path(os.getenv("AI_APP_CACHE_DIR", XDG_CACHE_HOME / APP_ID))
AI_APP_STATE_DIR = Path(os.getenv("AI_APP_STATE_DIR", XDG_STATE_HOME / APP_ID))

# Public constants you’ll actually use
CONFIG_DIR = AI_APP_CONFIG_DIR
DATA_DIR = AI_APP_DATA_DIR
CACHE_DIR = AI_APP_CACHE_DIR
STATE_DIR = AI_APP_STATE_DIR
LOG_DIR = STATE_DIR / "logs"  # common convention on Linux
PROFILES_DIR = DATA_DIR / "profiles"

# Reports live in the project tree but are git-ignored and never packaged
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "project_reports"


def ensure_runtime_tree() -> None:
    for p in (
        CONFIG_DIR,
        DATA_DIR,
        CACHE_DIR,
        STATE_DIR,
        LOG_DIR,
        PROFILES_DIR,
        REPORTS_DIR,
    ):
        p.mkdir(parents=True, exist_ok=True)
