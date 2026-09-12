def rowd(r):
    if r is None: return {}
    if isinstance(r, dict): return r
    try: return {k:r[k] for k in r.keys()}
    except Exception: return r

#!/usr/bin/env python3
import asyncio, os, sqlite3
from pathlib import Path
DB=os.environ.get("TGCHAT_DB","/var/lib/tgchat/tgchat.db")
SESS=Path("/var/lib/tgchat/sessions")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def log(msg,level="info"):
    c=db()
    c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,level TEXT,msg TEXT)")
    c.execute("INSERT INTO events(ts,level,msg) VALUES(datetime('now'),?,?)",(level,str(msg)[:500]))
    c.commit(); c.close(); print(msg,flush=True)

def norm(s):
    s=(s or "").strip()
    for p in ("https://","http://","t.me/","telegram.me/"):
        if s.lower().startswith(p): s=s[len(p):]
    return s.lstrip("@")

async def collect():
    from telethon import TelegramClient
    c=db()
    c.execute("CREATE TABLE IF NOT EXISTS pending_users(id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_account INTEGER,source_group TEXT,username TEXT,seen_at TEXT,UNIQUE(monitor_account,source_group,username))")
    binds=c.execute("SELECT * FROM identity_bindings WHERE enabled=1").fetchall()
    c.close()
    seen_windows=set()
    for b in binds:
        key=(rowd(b)["monitor_account"], rowd(b)["source_group"])
        if key in seen_windows: continue
        seen_windows.add(key)
        c=db()
        acc=c.execute("SELECT * FROM accounts WHERE id=?",(rowd(b)["monitor_account"],)).fetchone()
        api=c.execute("SELECT * FROM api_keys WHERE id=?",(acc["api_id"],)).fetchone() if acc and acc["api_id"] else None
        bound=c.execute("SELECT COUNT(*) FROM identity_bindings WHERE monitor_account=? AND source_group=?",key).fetchone()[0]
        pend=c.execute("SELECT COUNT(*) FROM pending_users WHERE monitor_account=? AND source_group=?",key).fetchone()[0]
        c.close()
        if not acc or not api:
            log("采集跳过 无API #%s"%rowd(b)["monitor_account"],"warn"); continue
        if bound>=5:
            continue
        cl=TelegramClient(str(SESS/("acc_%s.session"%rowd(b)["monitor_account"])), int(api["api_id"]), api["api_hash"])
        try:
            await cl.connect()
            if not await cl.is_user_authorized():
                log("采集失败 未登录 #%s"%rowd(b)["monitor_account"],"warn"); await cl.disconnect(); continue
            ent=await cl.get_entity(norm(rowd(b)["source_group"]))
            msgs=await cl.get_messages(ent, limit=20)
            added=0
            for m in msgs or []:
                if bound+pend+added>=5: break
                sender=await m.get_sender()
                uname=getattr(sender,"username",None)
                if not uname: continue
                name="@"+uname
                if name.lower()==norm(rowd(b).get("real_user") or "").lower() or uname.lower()==norm(rowd(b).get("real_user") or "").lower():
                    continue
                c=db()
                try:
                    c.execute("INSERT INTO pending_users(monitor_account,source_group,username,seen_at) VALUES(?,?,?,datetime('now'))",(rowd(b)["monitor_account"],rowd(b)["source_group"],name))
                    c.commit(); added+=1
                except Exception:
                    pass
                c.close()
            await cl.disconnect()
            if added: log("采集到 %s 个待绑定"%added)
        except Exception as e:
            log("采集异常 %s"%e,"error")
            try: await cl.disconnect()
            except Exception: pass

if __name__=="__main__":
    asyncio.run(collect())
