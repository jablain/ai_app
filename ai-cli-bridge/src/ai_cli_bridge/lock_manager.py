import json, os, time
from pathlib import Path
from .errors import E, die
ROOT=Path.home()/".ai_cli_bridge"
LOCKDIR=ROOT/"cache"/"locks"
def _alive(pid:int)->bool:
    try: os.kill(pid,0); return True
    except Exception: return False
def acquire(ai:str, conversation:str|None=None, force:bool=False):
    LOCKDIR.mkdir(parents=True, exist_ok=True)
    path=LOCKDIR/f"{ai}.lock"
    if path.exists():
        try:
            data=json.loads(path.read_text()); pid=int(data.get("pid",0))
        except: pid=0
        stale = (not _alive(pid)) or (time.time()-path.stat().st_mtime>86400)
        if not stale and not force: die(E.E005)
        try: path.unlink()
        except: pass
    fd=os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    with os.fdopen(fd,"w") as f:
        f.write(json.dumps({
            "version":"1.0","pid":os.getpid(),
            "created_at":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }))
    return path
def release(ai:str):
    path=LOCKDIR/f"{ai}.lock"
    try: path.unlink()
    except: pass
