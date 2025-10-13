"""Init command per spec Section 8.7."""
import sys
from pathlib import Path
from ..config import load, ensure_dirs
from ..errors import E, die


def run(ai_name: str):
    """
    Initialize AI target configuration.
    
    Per spec Section 8.7:
    - Normalize AI name
    - Create skeleton config & profile directory (0700)
    - Idempotent
    """
    ensure_dirs()
    
    # Normalize AI name: lowercase, [a-z0-9_-], collapse underscores, max 32
    ai_name = ai_name.lower().strip()
    ai_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in ai_name)
    while '__' in ai_name:
        ai_name = ai_name.replace('__', '_')
    ai_name = ai_name.strip('_-')[:32]
    
    if not ai_name:
        die(E.E003, "AI name cannot be empty after normalization")
    
    # Load or validate config exists
    try:
        cfg = load(ai_name)
        print(f"✓ Configuration loaded for '{ai_name}'", file=sys.stderr)
    except SystemExit:
        die(E.E003, f"No configuration found for '{ai_name}'. Create config file first at ~/.ai_cli_bridge/config/{ai_name}.json")
    
    # Ensure profile directory exists with correct permissions
    profile_dir = Path(cfg["_profile_dir"])
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.chmod(0o700)
    
    print(f"✓ Profile directory ready: {profile_dir}", file=sys.stderr)
    print(f"\nTo use: ai-cli-bridge open {ai_name}", file=sys.stderr)
    
    return 0
