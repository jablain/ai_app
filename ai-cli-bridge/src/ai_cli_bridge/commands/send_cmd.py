"""Send command using AI abstraction layer."""

import asyncio
import json as jsonlib
from ..ai import AIFactory


def run(
    ai_name: str,
    message: str,
    wait: bool = True,
    timeout: int = 120,
    json_out: bool = False,
    debug: bool = False
) -> int:
    """
    Send message via CDP connection using AI-specific implementation.
    
    Args:
        ai_name: AI target name (claude, chatgpt, gemini)
        message: Message text to send
        wait: Whether to wait for response
        timeout: Response timeout in seconds
        json_out: Whether to output JSON format
        debug: Enable debug output
        
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
    
    # Create AI instance
    try:
        ai = AIFactory.create(ai_name, cfg)
        ai.set_debug(debug)
    except NotImplementedError as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "not_implemented", "message": str(e)}, indent=2))
        else:
            print(f"✗ {e}")
        return 2
    
    # Execute send
    try:
        success, snippet, markdown, metadata = asyncio.run(
            ai.send_prompt(message, wait_for_response=wait, timeout_s=timeout)
        )
        
        if not success:
            error_msg = metadata.get("error", "unknown") if metadata else "unknown"
            if json_out:
                print(jsonlib.dumps({
                    "ok": False,
                    "error": error_msg,
                    **(metadata or {})
                }, indent=2))
            else:
                print(f"✗ Send failed: {error_msg}")
            return 1
        
        # Success output
        if json_out:
            print(jsonlib.dumps({
                "ok": True,
                "snippet": snippet,
                "markdown": markdown,
                **(metadata or {})
            }, indent=2))
        else:
            print("✓ Sent")
            if wait and metadata:
                elapsed_ms = metadata.get("elapsed_ms")
                if elapsed_ms is not None:
                    print(f"  elapsed: {elapsed_ms} ms")
                
                if snippet:
                    print("  response:")
                    for line in snippet.splitlines():
                        print(f"    {line}")
                else:
                    print("  (no response extracted)")
        
        return 0
        
    except NotImplementedError as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "not_implemented", "message": str(e)}, indent=2))
        else:
            print(f"✗ {e}")
        return 2
    except Exception as e:
        if json_out:
            print(jsonlib.dumps({"ok": False, "error": "exception", "message": str(e)}, indent=2))
        else:
            print(f"✗ Unexpected error: {e}")
        return 1
