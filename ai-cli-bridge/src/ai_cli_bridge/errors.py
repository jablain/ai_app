from enum import IntEnum
class Exit(IntEnum):
    OK=0; SESSION=1; CONFIG=2; DISPLAY=3; CONCURRENCY=4; IOFS=5
class E:
    E001=("E001","No graphical display detected. AI-CLI-Bridge cannot run headless.",Exit.DISPLAY)
    E002=("E002","Browser session not found or not ready.",Exit.SESSION)
    E003=("E003","Config parse/validation error.",Exit.CONFIG)
    E004=("E004","Selector not found or invalid.",Exit.CONFIG)
    E005=("E005","Concurrent session detected.",Exit.CONCURRENCY)
def die(err, extra=None):
    code,msg,exitc = err
    if extra: msg=f"{msg} {extra}"
    print(f"{code}: {msg}")
    raise SystemExit(exitc)
