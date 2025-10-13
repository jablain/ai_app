import asyncio
from ..config import load, ensure_dirs
from ..lock_manager import acquire, release
from ..browser_manager import launch_browser


def run(ai_name: str, conversation: str | None, force: bool):
    """
    Open command per spec Section 8.1:
    - Lock acquire
    - Launch browser
    - (Navigation & auth readiness handled inside launch_browser)
    """
    ensure_dirs()
    cfg = load(ai_name)
    
    lock = None
    try:
        lock = acquire(ai_name, conversation, force)
        asyncio.run(_go(cfg, conversation))
        return 0
    finally:
        if lock:
            release(ai_name)

async def _go(cfg, conversation):
    # conversation is already normalized by run(); keep this as a safety net
    conversation = (conversation or "").strip() or None

    # Hand the desired conversation URL to the browser layer.
    # launch_browser() will prefer this and avoid a redundant reload if already on Claude.
    if conversation:
        cfg["_conversation_url"] = conversation

    async with launch_browser(cfg) as page:
        # Do NOT navigate here — launch_browser handles navigation (or deliberately skips it).
        print("✓ Browser launched")
        try:
            cur = page.url
        except Exception:
            cur = "(unknown)"
        print(f"✓ Loaded: {cur}")
        print("✓ Ready (auth verified)")

