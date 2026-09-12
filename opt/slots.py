import sqlite3
from datetime import datetime, timedelta
DB="/var/lib/tgchat/tgchat.db"
def db():
    return sqlite3.connect(DB)
def now():
    return datetime.utcnow()
def parse(s):
    try: return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except Exception: return now()
def rotate():
    c=db()
    c.execute("CREATE TABLE IF NOT EXISTS active_slots(slot INTEGER PRIMARY KEY, username TEXT, last_ts TEXT)")
    pend=[r[0] for r in c.execute("SELECT username FROM pending_users ORDER BY id DESC")]
    maps=list(c.execute("SELECT src_user, ts FROM msg_map ORDER BY id DESC LIMIT 80"))
    last={}
    for u,ts in maps:
        if u not in last: last[u]=ts
    slots={r[0]:(r[1],r[2]) for r in c.execute("SELECT slot,username,last_ts FROM active_slots")}
    used=set()
    out=[]
    for i in range(1,4):
        u,ts = slots.get(i,(None,None))
        stale = (not u) or (u not in last) or (now()-parse(last.get(u) or ts or "2000-01-01 00:00:00")>timedelta(minutes=2))
        if stale:
            nxt=None
            for p in pend:
                if p not in used and p!=u:
                    nxt=p; break
            u=nxt or u
            ts=last.get(u) or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        used.add(u)
        c.execute("INSERT OR REPLACE INTO active_slots(slot,username,last_ts) VALUES(?,?,?)",(i,u,last.get(u) or ts))
        out.append((i,u,last.get(u) or ts))
    c.commit(); c.close()
    return out
if __name__=="__main__":
    print(rotate())
