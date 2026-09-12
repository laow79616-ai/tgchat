import sqlite3, random
from pathlib import Path
from telethon import TelegramClient
DB="/var/lib/tgchat/tgchat.db"
SESS=Path("/var/lib/tgchat/sessions")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

async def run():
    c=db()
    jobs=list(c.execute("SELECT * FROM bot_jobs WHERE enabled=1"))
    maps=[r for r in c.execute("SELECT src_user,text FROM msg_map ORDER BY id DESC LIMIT 40")
          if r["text"] and "kicked" not in (r["text"] or "").lower() and "bot" not in (r["src_user"] or "").lower()]
    if not jobs or not maps:
        c.close(); return
    job=jobs[0]
    ids=[int(x) for x in (job["active_ids"] or job["account_ids"] or "").split(",") if x.strip()][:3]
    if not ids:
        c.close(); return
    aid=ids[random.randint(0,len(ids)-1)]
    acc=c.execute("SELECT id,api_id,status FROM accounts WHERE id=?",(aid,)).fetchone()
    if not acc or acc["status"]!="ONLINE":
        c.close(); return
    api=c.execute("SELECT api_id,api_hash FROM api_keys WHERE id=?",(acc["api_id"],)).fetchone()
    text=(maps[random.randint(0,len(maps)-1)]["text"] or "")[:180]
    dest=job["dest_group"]
    c.close()
    if not text or not api:
        return
    cl=TelegramClient(str(SESS/("acc_%s.session"%aid)), int(api["api_id"]), api["api_hash"])
    await cl.connect()
    if await cl.is_user_authorized():
        await cl.send_message(dest, text)
        print("bot_reply #%s -> %s %s"%(aid, dest, text[:40]), flush=True)
    await cl.disconnect()
