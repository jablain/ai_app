import os
def has_display(): return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
def mode():
    if os.environ.get("WAYLAND_DISPLAY"): return "Wayland"
    if os.environ.get("DISPLAY"): return "X11"
    return "Unknown"
