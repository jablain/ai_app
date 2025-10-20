from ..config import ensure_dirs
from ..display import has_display, mode
def run(startup: bool = False, as_json: bool = False):
    ensure_dirs()
    if startup:
        print(f"✓ Display: {'Available' if has_display() else 'Unavailable'} ({mode()})")
        try:
            import playwright; playwright  # noqa
            print("✓ Playwright: installed")
        except Exception as e:
            print(f"✗ Playwright: NOT installed ({e})")
        return 0
    else:
        print("✓ Doctor (standard): full live checks come after open in the next step")
        return 0
