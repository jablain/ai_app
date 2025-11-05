#!/usr/bin/env python3
"""
Diagnostic tool to test context warning feature.
Run this while ai-chat-ui is running to see current context usage.
"""

import sys
import requests


def test_context_warning():
    print("=" * 70)
    print("Context Warning Feature Diagnostic")
    print("=" * 70)
    print()

    # Check if daemon is running
    try:
        response = requests.get("http://127.0.0.1:8000/status", timeout=2)
        status = response.json()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Daemon is not running!")
        print("   Start it with: ai-cli-bridge daemon start")
        return
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return

    print("✓ Daemon is running")
    print()

    # Check thresholds
    thresholds = status.get("daemon", {}).get("context_warning_thresholds", {})
    if thresholds:
        print("✓ Context warning thresholds configured:")
        print(f"   Yellow:  {thresholds.get('yellow', 'N/A')}%")
        print(f"   Orange:  {thresholds.get('orange', 'N/A')}%")
        print(f"   Red:     {thresholds.get('red', 'N/A')}%")
    else:
        print("❌ WARNING: No context_warning_thresholds in daemon response")
        print("   Check daemon_config.toml has [features.context_warning] section")
    print()

    # Check AI instances
    ais = status.get("ais", {})
    if not ais:
        print("ℹ️  No AI instances active yet")
        print("   Start a chat in ai-chat-ui to see context usage")
        return

    print(f"Active AI instances: {', '.join(ais.keys())}")
    print()

    # Check each AI's context usage
    for ai_name, ai_data in ais.items():
        print(f"AI: {ai_name}")
        print("-" * 40)

        ctw = ai_data.get("ctaw_size", 0)
        ctw_used_pct = ai_data.get("ctaw_usage_percent", 0)
        connected = ai_data.get("connected", False)

        print(f"   Connected: {connected}")
        print(f"   Context Window: {ctw:,} tokens")
        print(f"   Usage: {ctw_used_pct:.1f}%")
        print()

        # Determine what should be displayed
        yellow = thresholds.get("yellow", 70)
        orange = thresholds.get("orange", 85)
        red = thresholds.get("red", 95)

        if ctw_used_pct >= red:
            display = f"⚠️  Usage: {ctw_used_pct:.1f}% (CRITICAL)"
            color = "RED"
        elif ctw_used_pct >= orange:
            display = f"⚠️  Usage: {ctw_used_pct:.1f}% (HIGH)"
            color = "ORANGE"
        elif ctw_used_pct >= yellow:
            display = f"⚠️  Usage: {ctw_used_pct:.1f}% (WARNING)"
            color = "ORANGE"
        else:
            display = f"✓ Usage: {ctw_used_pct:.1f}% (OK)"
            color = "GREEN"

        print(f"   Expected UI Display:")
        print(f'     "{display}"')
        print(f"     Color: {color}")
        print()

    print("=" * 70)
    print()
    print("Color Legend:")
    print(f"  ✓ GREEN:  0-{thresholds.get('yellow', 70) - 1}% (OK)")
    print(
        f"  ⚠️  ORANGE: {thresholds.get('yellow', 70)}-{thresholds.get('orange', 85) - 1}% (WARNING)"
    )
    print(f"  ⚠️  ORANGE: {thresholds.get('orange', 85)}-{thresholds.get('red', 95) - 1}% (HIGH)")
    print(f"  ⚠️  RED:    {thresholds.get('red', 95)}%+ (CRITICAL)")


if __name__ == "__main__":
    test_context_warning()
