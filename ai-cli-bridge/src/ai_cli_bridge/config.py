import json, re, os
from pathlib import Path
from .errors import E, die

ROOT = Path.home() / ".ai_cli_bridge"
CONF = ROOT / "config"
DEFAULT_TIMEOUTS = {
    "browser_launch": 30,
    "page_load": 30,
    "response_wait": 120,
    "file_upload": 30,
    "response_stability_ms": 2000,
}

def load(ai: str):
    p = CONF / f"{ai}.json"
    try:
        data = json.loads(p.read_text())
    except Exception as e:
        die(E.E003, f"(read {p}): {e}")

    # basic validation (FIX: correct regex with single backslash for dot)
    try:
        sv = data.get("schema_version", "1.0.0")
        if not re.match(r"^1\.[0-9]+\.[0-9]+$", sv or ""):
            raise AssertionError(f"schema_version invalid: {sv!r}")
        if not isinstance(data.get("selectors"), dict):
            raise AssertionError("selectors is not an object/dict")
        bu = data.get("base_url")
        if not (isinstance(bu, str) and bu.startswith("http")):
            raise AssertionError(f"base_url invalid: {bu!r}")
    except Exception as e:
        die(E.E003, f"(validate {p}): {e}")

    # timeouts merged with defaults
    t = {**DEFAULT_TIMEOUTS, **(data.get("timeouts") or {})}
    data["timeouts"] = t

    # profile dir
    prof = ROOT / "data" / "profiles" / ai
    prof.mkdir(parents=True, exist_ok=True)
    data["_profile_dir"] = str(prof)
    return data

def ensure_dirs():
    for d in ["config", "data/profiles", "cache/locks", "logs"]:
        (ROOT / Path(d)).mkdir(parents=True, exist_ok=True)
    for d in [ROOT, ROOT / "config", ROOT / "data", ROOT / "cache"]:
        try:
            os.chmod(d, 0o700)
        except Exception:
            pass
