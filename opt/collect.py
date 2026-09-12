#!/usr/bin/env python3
import asyncio, os, sqlite3
from pathlib import Path
from telethon import TelegramClient

DB = os.environ.get("TGCHAT_DB", "/var/lib/tgchat/tgchat.db")
SESS = Path("/var/lib/tgchat/sessions")

def rowd(r):
    if r is None:
        return {}
    if isinstance(r, dict):
        return r
    try:
        return {k: r[k] for k in r.keys()}
    except Exception:
        return r

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def log(msg, level="info"):
    print(msg, flush=True)
    c = db()
    c.execute("INSERT INTO events(ts,level,msg) VALUES(datetime('now'),?,?)", (level, str(msg)[:300]))
    c.commit()
    c.close()

def norm(s):
    return (s or "").replace("https://t.me/", "").replace("http://t.me/", "").replace("@", "").strip().lower()

def client(aid):
    c = db()
    acc = c.execute("SELECT id,api_id FROM accounts WHERE id=?", (aid,)).fetchone()
    if not acc:
        c.close()
        raise RuntimeError("无账号 #%s" % aid)
    api = c.execute("SELECT api_id,api_hash FROM api_keys WHERE id=?", (acc["api_id"],)).fetchone()
    c.close()
    if not api:
        raise RuntimeError("无API #%s" % aid)
    return TelegramClient(str(SESS / ("acc_%s.session" % aid)), int(api["api_id"]), api["api_hash"])

async def collect():
    c = db()
    c.execute("CREATE TABLE IF NOT EXISTS pending_users(id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_account INTEGER,source_group TEXT,username TEXT,seen_at TEXT,UNIQUE(monitor_account,source_group,username))")
    c.execute("CREATE TABLE IF NOT EXISTS msg_map(id INTEGER PRIMARY KEY AUTOINCREMENT, win_tag TEXT, src_user TEXT, text TEXT, ts TEXT)")
    binds = [rowd(x) for x in c.execute("SELECT * FROM identity_bindings WHERE enabled=1").fetchall()]
    c.close()
    for b in binds:
        aid = b.get("monitor_account")
        g = b.get("source_group") or ""
        if not aid or not g:
            continue
        try:
            cl = client(aid)
            await cl.connect()
            if not await cl.is_user_authorized():
                raise RuntimeError("未登录 #%s" % aid)
            ent = await cl.get_entity(g)
            msgs = await cl.get_messages(ent, limit=20)
            added = 0
            saved = 0
            for m in msgs or []:
                sender = await m.get_sender()
                uname = getattr(sender, "username", None) if sender else None
                name = ("@" + uname) if uname else ("id:" + str(getattr(sender, "id", "") if sender else ""))
                txt = (getattr(m, "message", None) or "")
                if txt:
                    c2 = db()
                    c2.execute("INSERT INTO msg_map(win_tag,src_user,text,ts) VALUES(?,?,?,datetime('now'))", (str(b.get("tag") or "1"), name, txt[:500]))
                    c2.commit()
                    c2.close()
                    saved += 1
                if uname:
                    c2 = db()
                    try:
                        c2.execute("INSERT INTO pending_users(monitor_account,source_group,username,seen_at) VALUES(?,?,?,datetime('now'))", (aid, g, name))
                        c2.commit()
                        added += 1
                    except Exception:
                        pass
                    c2.close()
            await cl.disconnect()
            log("采集待绑定+%s 正文+%s" % (added, saved))
        except Exception as e:
            log("采集异常 %s" % e, "error")
            try:
                await cl.disconnect()
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(collect())
