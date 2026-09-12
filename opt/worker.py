FLOOD_UNTIL={}
ENTITY_CACHE={}
#!/usr/bin/env python3
import asyncio, os, sqlite3, time
from pathlib import Path

DB = os.environ.get("TGCHAT_DB", "/var/lib/tgchat/tgchat.db")
SESS = Path("/var/lib/tgchat/sessions")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def log(msg, level="info"):
    c = db()
    c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,level TEXT,msg TEXT)")
    c.execute("INSERT INTO events(ts,level,msg) VALUES(datetime('now'),?,?)", (level, str(msg)[:500]))
    c.commit(); c.close()
    print(msg, flush=True)

def norm(s):
    s = (s or "").strip()
    for p in ("https://", "http://", "t.me/", "telegram.me/"):
        if s.lower().startswith(p):
            s = s[len(p):]
    if s.startswith("@"):
        s = s[1:]
    return s

async def client_for(aid):
    from telethon import TelegramClient
    c = db()
    acc = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    api = None
    if acc and acc["api_id"]:
        api = c.execute("SELECT * FROM api_keys WHERE id=?", (acc["api_id"],)).fetchone()
    c.close()
    if not acc or not api:
        raise RuntimeError("账号或API不存在 #%s" % aid)
    cl = TelegramClient(str(SESS / ("acc_%s.session" % aid)), int(api["api_id"]), api["api_hash"])
    await cl.connect()
    if not await cl.is_user_authorized():
        await cl.disconnect()
        raise RuntimeError("未登录 #%s" % aid)
    return cl

async def join(cl, link, tag):
    from telethon.tl.functions.channels import JoinChannelRequest
    name = norm(link)
    try:
        ent = await cl.get_entity(name)
        try:
            await cl(JoinChannelRequest(ent))
            log("进群成功 %s -> %s" % (tag, name))
        except Exception as e:
            log("进群跳过 %s %s %s" % (tag, name, e), "warn")
        return ent
    except Exception as e:
        log("解析群失败 %s %s %s" % (tag, name, e), "error")
        return None

async def once():
    try:
        import slots as _sl; _sl.rotate()
    except Exception as _e:
        log('slot '+str(_e),'warn')

    c = db()
    c.execute("CREATE TABLE IF NOT EXISTS identity_bindings(id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_account INTEGER,source_group TEXT,real_user TEXT,mirror_account INTEGER,dest_group TEXT,enabled INTEGER DEFAULT 1)")
    rows = c.execute("SELECT * FROM identity_bindings WHERE enabled=1").fetchall()
    c.close()
    if not rows:
        log("无身份绑定")
        return
    n = 0
    for b in rows:
        try:
            mon = await client_for(b["monitor_account"])
            mir = await client_for(b["mirror_account"])
            src = await join(mon, b["source_group"], "监听#%s" % b["monitor_account"])
            dst = await join(mir, b["dest_group"], "镜像#%s" % b["mirror_account"])
            if not src or not dst:
                await mon.disconnect(); await mir.disconnect()
                continue
            want = norm(b["real_user"]).lower()
            allow=set()
            try:
                import sqlite3 as _s2
                _c2=_s2.connect('/var/lib/tgchat/tgchat.db')
                allow=set((r[0] or '').lower() for r in _c2.execute('SELECT username FROM active_slots') if r[0])
                _c2.close()
            except Exception:
                allow=set()
            msgs = await mon.get_messages(src, limit=5)
            for m in reversed(list(msgs or [])):
                if not m or not m.id:
                    continue
                sender = await m.get_sender()
                uname = (getattr(sender, "username", None) or "")
                uid = str(getattr(sender, "id", "") or "")
                if allow and (("@"+uname.lower()) not in allow) and (uname.lower() not in allow):
                    continue
                if want and want not in ("auto","") and want not in (uname.lower(), str(uid), "@"+uname.lower()):
                    continue
                key = "fwd:%s:%s" % (b["id"], m.id)
                c = db()
                if c.execute("SELECT 1 FROM events WHERE msg=?", (key,)).fetchone():
                    c.close(); continue
                text = m.message or ""
                kws = c.execute("SELECT src,dst FROM keywords").fetchall() if True else []
                try:
                    for k in c.execute("SELECT src,dst FROM keywords").fetchall():
                        if k["src"]:
                            text = text.replace(k["src"], k["dst"] or "")
                except Exception:
                    pass
                if text:
                    await mir.send_message(dst, text)
                    n += 1
                    log("转发 %s" % ((text or "")[:80]))
                c.execute("INSERT INTO events(ts,level,msg) VALUES(datetime('now'),'info',?)", (key,))
                c.commit(); c.close()
            await mon.disconnect(); await mir.disconnect()
        except Exception as e:
            log("窗口失败 id=%s %s" % (b["id"], e), "error")
    if n:
        log("本轮转发 %s 条" % n)

async def main():
    log("worker identity start")
    while True:
        try:
            await once()
            try:
                from collect import collect as _col
                await _col()
            except Exception as _e:
                log('collect '+str(_e),'warn')
            try:
                from bot_reply import run as _br
                await _br()
            except Exception as _be:
                log('bot_reply '+str(_be),'warn')
        except Exception as e:
            log("loop %s" % e, "error")
        await asyncio.sleep(8)

if __name__ == "__main__":
    asyncio.run(main())

# --- appended collector (safe if main already loops) ---
