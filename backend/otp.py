import os, asyncio
from pathlib import Path
SESS = Path("/var/lib/tgchat/sessions"); SESS.mkdir(parents=True, exist_ok=True)
PENDING = {}
def sp(aid): return str(SESS / f"acc_{aid}.session")
def send_code(api_id, api_hash, phone, aid):
    async def _():
        from telethon import TelegramClient
        ph = phone.strip() if phone.startswith("+") else "+"+phone.strip()
        c = TelegramClient(sp(aid), int(api_id), api_hash)
        await c.connect()
        try:
            r = await c.send_code_request(ph)
            PENDING[int(aid)] = {"phone": ph, "hash": r.phone_code_hash, "api_id": int(api_id), "api_hash": api_hash}
            return {"ok": True, "phone": ph}
        finally:
            await c.disconnect()
    return asyncio.run(_())
def sign_in(aid, code, password=""):
    async def _():
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
        st = PENDING.get(int(aid))
        if not st: raise RuntimeError("请先发送验证码")
        c = TelegramClient(sp(aid), st["api_id"], st["api_hash"])
        await c.connect()
        try:
            try:
                me = await c.sign_in(st["phone"], code.strip(), phone_code_hash=st["hash"])
            except SessionPasswordNeededError:
                if not password: raise RuntimeError("该号开启二次验证，请填写密码")
                me = await c.sign_in(password=password)
            return {"ok": True, "status": "ONLINE", "telegram_user_id": me.id, "username": me.username or ""}
        finally:
            await c.disconnect()
    return asyncio.run(_())
