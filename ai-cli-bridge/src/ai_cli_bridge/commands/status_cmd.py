"""Status command using AI abstraction layer."""

import asyncio
import json as jsonlib
from ..ai import AIFactory


def run(ai_name: str, json_out: bool = False) -> int:
    """
    Get status of AI session.
    
    Args:
        ai_name: AI target name (claude, chatgpt, gemini)
        json_out: Whether to output JSON format
        
    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Get AI class and its default configuration
    try:
        ai_class = AIFactory.get_class(ai_name)
        cfg = ai_class.get_default_config()
    except ValueError as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "unknown_ai", "message": str(e)}, indent=2))
        else:
            print(f"✗ {e}")
        return 2
    
    try:
        ai = AIFactory.create(ai_name, cfg)
        status = asyncio.run(ai.get_status())
        
        if json_out:
            print(jsonlib.dumps(status, indent=2))
        else:
            print(f"AI Target: {status.get('ai_target', 'unknown')}")
            print(f"Connected: {status.get('connected', False)}")
            print(f"CDP Source: {status.get('cdp_source', 'none')}")
            
            if status.get('cdp_url'):
                print(f"CDP URL: {status['cdp_url']}")
            
            if status.get('last_page_url'):
                print(f"Page URL: {status['last_page_url']}")
            
            print(f"Message Count: {status.get('message_count', 0)}")
            
            if 'session_duration_s' in status:
                duration = status['session_duration_s']
                print(f"Session Duration: {duration:.1f}s")
        
        return 0
        
    except ValueError as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "unknown_ai", "message": str(e)}, indent=2))
        else:
            print(f"✗ {e}")
        return 2
    except Exception as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "exception", "message": str(e)}, indent=2))
        else:
            print(f"✗ Unexpected error: {e}")
        return 1
