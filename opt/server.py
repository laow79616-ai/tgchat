#!/usr/bin/env python3
import json, os, sqlite3, sys
sys.path.insert(0,'/opt/tgchat-live')
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = "/var/lib/tgchat/tgchat.db"
os.makedirs("/var/lib/tgchat", exist_ok=True)

def init():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS api_keys(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,api_id TEXT,api_hash TEXT,account_id INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS ips(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,host TEXT,port INTEGER,username TEXT,password TEXT,line TEXT,account_id INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,display_name TEXT,phone TEXT,role TEXT,status TEXT,api_id INTEGER,ip_id INTEGER)")
    c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def sendj(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self): self.sendj(200, {"ok": True})
    def do_GET(self):
        _f=self.path.split("?")[0].rstrip("/")
        if _f=="/api/fwds":
            db=__import__("sqlite3").connect("/var/lib/tgchat/tgchat.db")
            rows=[{"id":r[0],"ts":r[1],"msg":r[2]} for r in db.execute("SELECT id,ts,msg FROM events WHERE msg LIKE '转发%' ORDER BY id DESC LIMIT 30")]
            self.sendj(200,rows); db.close(); return
        _bj=self.path.split("?")[0].rstrip("/")
        if _bj=="/api/botjobs":
            db=__import__("sqlite3").connect("/var/lib/tgchat/tgchat.db")
            db.execute("CREATE TABLE IF NOT EXISTS bot_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,dest_group TEXT,account_ids TEXT,active_ids TEXT,note TEXT,enabled INTEGER DEFAULT 1)")
            rows=[]
            for r in db.execute("SELECT id,dest_group,account_ids,active_ids,note,enabled FROM bot_jobs ORDER BY id DESC"):
                rows.append({"id":r[0],"dest_group":r[1],"account_ids":r[2],"active_ids":r[3],"note":r[4],"enabled":r[5]})
            self.sendj(200,rows); db.close(); return
        _sl=self.path.split("?")[0].rstrip("/")
        if _sl=="/api/slots":
            db=__import__("sqlite3").connect("/var/lib/tgchat/tgchat.db")
            try:
                rows=[{"slot":r[0],"username":r[1],"last_ts":r[2]} for r in db.execute("SELECT slot,username,last_ts FROM active_slots ORDER BY slot")]
            except Exception:
                rows=[]
            self.sendj(200,rows); db.close(); return
        _g=self.path.split("?")[0].rstrip("/")
        if _g=="/api/ipbinds":
            db=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            db.execute("CREATE TABLE IF NOT EXISTS ip_binds(ip_id INTEGER, account_id INTEGER, PRIMARY KEY(ip_id,account_id))")
            rows=[{"ip_id":r[0],"account_id":r[1]} for r in db.execute("SELECT ip_id,account_id FROM ip_binds")]
            self.sendj(200,rows); db.close(); return
        if self.path.split("?")[0].rstrip("/")=="/api/msgmap/speakers":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            c.execute("CREATE TABLE IF NOT EXISTS msg_speakers(account_id INTEGER PRIMARY KEY,status TEXT)")
            self.sendj(200,[dict(x) for x in c.execute("SELECT * FROM msg_speakers").fetchall()]); c.close(); return
        _gm=self.path.split("?")[0].rstrip("/")
        if _gm=="/api/msgmap":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            c.execute("CREATE TABLE IF NOT EXISTS msg_map(id INTEGER PRIMARY KEY AUTOINCREMENT,win_tag TEXT,src_user TEXT,text TEXT,ts TEXT)")
            rows=[dict(x) for x in c.execute("SELECT * FROM msg_map ORDER BY id DESC LIMIT 80").fetchall()]
            self.sendj(200,rows); c.close(); return
        if _gm=="/api/msgmap/analyze":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            rows=list(c.execute("SELECT * FROM msg_map ORDER BY id DESC LIMIT 40").fetchall())
            tips=[]
            if not rows:
                tips.append("消息库为空：等 #1 主线成功转发后才会有记录。现在不要开 worker 解析用户名。")
            else:
                tips.append("库内 %s 条。相似句可 1:1 复用，不要现编。" % len(rows))
                last=rows[0]["text"] or ""
                sim=[r for r in rows[1:] if last and (last[:12] in (r["text"] or "") or (r["text"] or "")[:12] in last)]
                tips.append("与最新一条前缀相近：%s 条" % len(sim))
            self.sendj(200,{"tips":tips,"count":len(rows)}); c.close(); return

        _g=self.path.split("?")[0].rstrip("/")
        if _g=="/api/worker/status":
            import subprocess
            st=subprocess.getoutput("systemctl is-active tgchat-worker || true")
            self.sendj(200,{"active":st.strip()=="active","state":st.strip()}); return
        if _g=="/api/windows":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            acc={r["id"]:r for r in c.execute("SELECT * FROM accounts").fetchall()}
            flags={r["account_id"]:r for r in c.execute("CREATE TABLE IF NOT EXISTS account_flags(account_id INTEGER PRIMARY KEY,cooling INTEGER,reason TEXT); SELECT * FROM account_flags").fetchall()} if False else {}
            try:
                flags={r["account_id"]:dict(r) for r in c.execute("SELECT * FROM account_flags").fetchall()}
            except Exception:
                flags={}
            out=[]
            for b in c.execute("SELECT * FROM identity_bindings ORDER BY id").fetchall():
                miss=[]
                mon=acc.get(b["monitor_account"]); mir=acc.get(b["mirror_account"])
                if not b["source_group"]: miss.append("缺监听群")
                if not b["dest_group"]: miss.append("缺目标群")
                if not b["real_user"]: miss.append("缺源用户")
                if not mon: miss.append("监听号不存在")
                elif str(mon["status"] or "").upper()!="ONLINE": miss.append("监听号未在线")
                if not mir: miss.append("镜像号不存在")
                elif str(mir["status"] or "").upper()!="ONLINE": miss.append("镜像号未在线")
                if mon and flags.get(mon["id"],{}).get("cooling"): miss.append("监听号冷却中")
                if mir and flags.get(mir["id"],{}).get("cooling"): miss.append("镜像号冷却中")
                if b["monitor_account"]==b["mirror_account"]: miss.append("监听号与镜像号不能相同")
                out.append({**dict(b),"missing":miss,"ready":len(miss)==0})
            self.sendj(200,out); c.close(); return
        if _g=="/api/window_messages":
            q=self.path.split("id=")[-1].split("&")[0] if "id=" in self.path else ""
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            like="%bind="+q+"%" if q else "fwd:%"
            rows=c.execute("SELECT * FROM events WHERE msg LIKE ? OR msg LIKE ? ORDER BY id DESC LIMIT 50",("%bind="+q+"%","fwd:"+q+":%")).fetchall() if q else []
            if q:
                rows=c.execute("SELECT * FROM events WHERE msg LIKE ? OR msg LIKE ? ORDER BY id DESC LIMIT 80",("%bind="+q+"%","fwd:"+q+":%")).fetchall()
            self.sendj(200,[dict(x) for x in rows]); c.close(); return
        _g=self.path.split('?')[0].rstrip('/')
        if _g=='/api/pending':
            c=sqlite3.connect('/var/lib/tgchat/tgchat.db'); c.row_factory=sqlite3.Row
            self.sendj(200,[dict(x) for x in c.execute('SELECT * FROM pending_users ORDER BY id DESC LIMIT 50').fetchall()]); c.close(); return

        path0=self.path.split("?")[0].rstrip("/") or "/"
        if path0=="/api/identities":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            c.execute("CREATE TABLE IF NOT EXISTS identity_bindings(id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_account INTEGER,source_group TEXT,real_user TEXT,mirror_account INTEGER,dest_group TEXT,enabled INTEGER DEFAULT 1,UNIQUE(monitor_account,source_group,real_user))")
            self.sendj(200,[dict(x) for x in c.execute("SELECT * FROM identity_bindings ORDER BY id DESC").fetchall()]); c.close(); return

        # GET binds
        path=self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/api/binds","/api/keywords","/api/events","/api/dialogs"):
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            if path=="/api/dialogs":
                aid=0
                if "account_id=" in self.path:
                    aid=int(self.path.split("account_id=")[-1].split("&")[0] or 0)
                try:
                    import sys; sys.path.insert(0,"/opt/tgchat-live")
                    from worker import list_dialogs
                    import asyncio
                    self.sendj(200, asyncio.run(list_dialogs(aid)))
                except Exception as e:
                    self.sendj(400,{"detail":str(e)})
                c.close(); return
            if path=="/api/binds":
                c.execute("CREATE TABLE IF NOT EXISTS binds(id INTEGER PRIMARY KEY AUTOINCREMENT,src_account INTEGER,src_chat TEXT,dst_account INTEGER,dst_chat TEXT,enabled INTEGER DEFAULT 1)")
                self.sendj(200,[dict(x) for x in c.execute("SELECT * FROM binds").fetchall()]); c.close(); return
            if path=="/api/keywords":
                c.execute("CREATE TABLE IF NOT EXISTS keywords(id INTEGER PRIMARY KEY AUTOINCREMENT,src TEXT,dst TEXT,enabled INTEGER DEFAULT 1)")
                self.sendj(200,[dict(x) for x in c.execute("SELECT * FROM keywords").fetchall()]); c.close(); return
            if path=="/api/events":
                c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,level TEXT,msg TEXT)")
                self.sendj(200,[dict(x) for x in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT 80").fetchall()]); c.close(); return

        p = self.path.split("?")[0].rstrip("/") or "/"
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        if p in ("/api/health", "/health"):
            self.sendj(200, {"ok": True, "mode": "live"})
        elif p == "/api/overview":
            a=list(c.execute("SELECT * FROM accounts")); k=list(c.execute("SELECT * FROM api_keys")); i=list(c.execute("SELECT * FROM ips"))
            self.sendj(200, {"accounts":len(a),"online":0,"api_total":len(k),"api_free":sum(1 for x in k if not x["account_id"]),"ip_total":len(i),"ip_free":sum(1 for x in i if not x["account_id"]),"bound_pairs":0})
        elif p == "/api/apis":
            self.sendj(200, [dict(x) for x in c.execute("SELECT * FROM api_keys")])
        elif p == "/api/ips":
            self.sendj(200, [dict(x) for x in c.execute("SELECT * FROM ips")])
        elif p == "/api/accounts":
            self.sendj(200, [dict(x) for x in c.execute("SELECT * FROM accounts")])
        elif p == "/api/lines":
            self.sendj(200, [])
        else:
            self.sendj(404, {"detail":"Not Found","path":p})
        c.close()
    def do_POST(self):
        _bj=self.path.split("?")[0].rstrip("/")
        if _bj=="/api/botjobs":
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            ids=[str(x) for x in (body.get("account_ids") or [])]
            act=ids[:3]
            db=__import__("sqlite3").connect("/var/lib/tgchat/tgchat.db")
            db.execute("CREATE TABLE IF NOT EXISTS bot_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,dest_group TEXT,account_ids TEXT,active_ids TEXT,note TEXT,enabled INTEGER DEFAULT 1)")
            db.execute("INSERT INTO bot_jobs(dest_group,account_ids,active_ids,note,enabled) VALUES(?,?,?,?,1)",
                       (body.get("dest_group") or "", ",".join(ids), ",".join(act), body.get("note") or ""))
            db.commit(); self.sendj(200,{"ok":True,"active":act}); db.close(); return
        if _bj.startswith("/api/botjobs/") and _bj.endswith("/delete"):
            iid=int(_bj.split("/")[3])
            db=__import__("sqlite3").connect("/var/lib/tgchat/tgchat.db")
            db.execute("DELETE FROM bot_jobs WHERE id=?",(iid,)); db.commit(); db.close()
            self.sendj(200,{"ok":True}); return
        _b=self.path.split("?")[0].rstrip("/")
        if _b.startswith("/api/ips/") and _b.endswith("/bind"):
            iid=int(_b.split("/")[3])
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            ids=[int(x) for x in (body.get("account_ids") or [])]
            db=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            db.execute("CREATE TABLE IF NOT EXISTS ip_binds(ip_id INTEGER, account_id INTEGER, PRIMARY KEY(ip_id,account_id))")
            db.execute("DELETE FROM ip_binds WHERE ip_id=?",(iid,))
            for aid in ids:
                db.execute("INSERT OR REPLACE INTO ip_binds(ip_id,account_id) VALUES(?,?)",(iid,aid))
            db.commit(); self.sendj(200,{"ok":True,"ip":iid,"n":len(ids)}); db.close(); return
        _s=self.path.split("?")[0].rstrip("/")
        if _s.startswith("/api/identities/") and _s.endswith("/start"):
            iid=int(_s.split("/")[3])
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            try: c.execute("UPDATE identity_bindings SET enabled=1 WHERE id=?",(iid,))
            except Exception:
                try: c.execute("UPDATE identities SET enabled=1 WHERE id=?",(iid,))
                except Exception as e:
                    self.sendj(400,{"detail":str(e)}); c.close(); return
            c.commit(); self.sendj(200,{"ok":True,"id":iid,"enabled":1}); c.close(); return
        _pn=self.path.split("?")[0].rstrip("/")
        if _pn.startswith("/api/identities/") and _pn.endswith("/note"):
            iid=int(_pn.split("/")[3])
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            try: c.execute("ALTER TABLE identity_bindings ADD COLUMN note TEXT DEFAULT ''")
            except Exception: pass
            c.execute("UPDATE identity_bindings SET note=? WHERE id=?",(body.get("note") or "",iid))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        _pn=self.path.split("?")[0].rstrip("/")
        if _pn.startswith("/api/ips/") and _pn.endswith("/note"):
            iid=int(_pn.split("/")[3])
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            try: c.execute("ALTER TABLE ips ADD COLUMN note TEXT DEFAULT ''")
            except Exception: pass
            c.execute("UPDATE ips SET note=? WHERE id=?",(body.get("note") or "",iid))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        _pn=self.path.split("?")[0].rstrip("/")
        if _pn.startswith("/api/accounts/") and _pn.endswith("/note"):
            aid=int(_pn.split("/")[3])
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            try: c.execute("ALTER TABLE accounts ADD COLUMN note TEXT DEFAULT ''")
            except Exception: pass
            c.execute("UPDATE accounts SET note=? WHERE id=?",(body.get("note") or "",aid))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        _pi=self.path.split("?")[0].rstrip("/")
        if _pi.startswith("/api/ips/") and _pi.endswith("/bind"):
            iid=int(_pi.split("/")[3])
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            ids=body.get("account_ids") or body.get("ids") or []
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            for a in ids:
                try: c.execute("UPDATE accounts SET ip_id=? WHERE id=?",(iid,int(a)))
                except Exception: pass
            c.commit(); self.sendj(200,{"ok":True,"ip":iid,"n":len(ids)}); c.close(); return
        if self.path.split("?")[0].rstrip("/")=="/api/msgmap/speakers":
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b"{}")
            except Exception: body={}
            ids=list(dict.fromkeys([int(x) for x in (body.get("ids") or []) if str(x).isdigit()]))[:3]
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            c.execute("CREATE TABLE IF NOT EXISTS msg_speakers(account_id INTEGER PRIMARY KEY,status TEXT)")
            c.execute("DELETE FROM msg_speakers")
            for i,a in enumerate(ids):
                c.execute("INSERT INTO msg_speakers(account_id,status) VALUES(?,?)",(a,"工作中" if i<3 else "待命"))
            c.commit(); self.sendj(200,{"ok":True,"n":len(ids)}); c.close(); return
        _pm=self.path.split("?")[0].rstrip("/")
        if _pm=="/api/monitor/rotate":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            c.execute("CREATE TABLE IF NOT EXISTS monitor_pool(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER UNIQUE,active INTEGER DEFAULT 0,cooling INTEGER DEFAULT 0,reason TEXT,until_ts TEXT)")
            cur=c.execute("SELECT * FROM monitor_pool WHERE active=1").fetchone()
            nxt=c.execute("SELECT * FROM monitor_pool WHERE cooling=0 AND active=0 ORDER BY id LIMIT 1").fetchone()
            if cur:
                c.execute("UPDATE monitor_pool SET active=0,cooling=1,reason=?,until_ts=datetime('now','+90 minutes') WHERE id=?",("FloodWait rotate",cur["id"]))
            if nxt:
                c.execute("UPDATE monitor_pool SET active=1 WHERE id=?",(nxt["id"],))
                msg="监听切换 %s -> %s"%(cur["account_id"] if cur else "-", nxt["account_id"])
            else:
                msg="监听切换失败：没有可用备用号"
            c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,level TEXT,msg TEXT)")
            c.execute("INSERT INTO events(ts,level,msg) VALUES(datetime('now'),'warn',?)",(msg,))
            c.commit(); self.sendj(200,{"ok":True,"msg":msg}); c.close(); return

        _p=self.path.split("?")[0].rstrip("/")
        if _p=="/api/worker/start":
            import subprocess
            subprocess.call(["systemctl","start","tgchat-worker"])
            self.sendj(200,{"ok":True,"state":subprocess.getoutput("systemctl is-active tgchat-worker")}); return
        if _p=="/api/worker/stop":
            import subprocess
            subprocess.call(["systemctl","stop","tgchat-worker"])
            self.sendj(200,{"ok":True,"state":"stopped"}); return
        _p=self.path.split('?')[0].rstrip('/')
        if _p=='/api/pending/assign':
            raw=self.rfile.read(int(self.headers.get('Content-Length') or 0) or 0)
            import json as _j
            try: body=_j.loads(raw or b'{}')
            except Exception: body={}
            c=sqlite3.connect('/var/lib/tgchat/tgchat.db'); c.row_factory=sqlite3.Row
            pid=int(body.get('pending_id') or 0); mid=int(body.get('mirror_account') or 0)
            row=c.execute('SELECT * FROM pending_users WHERE id=?',(pid,)).fetchone()
            if not row: self.sendj(400,{'detail':'待绑定不存在'}); c.close(); return
            n=c.execute('SELECT COUNT(*) FROM identity_bindings WHERE monitor_account=? AND source_group=?',(row['monitor_account'],row['source_group'])).fetchone()[0]
            if n>=5: self.sendj(400,{'detail':'该窗口源用户已满5个'}); c.close(); return
            used=c.execute('SELECT COUNT(*) FROM identity_bindings WHERE dest_group=? AND mirror_account=?',(body.get('dest_group') or '', mid)).fetchone()[0]
            c.execute('INSERT INTO identity_bindings(monitor_account,source_group,real_user,mirror_account,dest_group) VALUES(?,?,?,?,?)',(row['monitor_account'],row['source_group'],row['username'],mid,(body.get('dest_group') or '')))
            c.execute('DELETE FROM pending_users WHERE id=?',(pid,)); c.commit(); self.sendj(200,{'ok':True}); c.close(); return

        _p=self.path.split("?")[0].rstrip("/")
        if _p=="/api/identities":
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db"); c.row_factory=sqlite3.Row
            raw=self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0)
            try: body=json.loads(raw or b"{}")
            except Exception: body={}
            c.execute("CREATE TABLE IF NOT EXISTS identity_bindings(id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_account INTEGER,source_group TEXT,real_user TEXT,mirror_account INTEGER,dest_group TEXT,enabled INTEGER DEFAULT 1)")
            try:
                c.execute("INSERT INTO identity_bindings(monitor_account,source_group,real_user,mirror_account,dest_group) VALUES(?,?,?,?,?)",
                          (int(body.get("monitor_account") or 0),(body.get("source_group") or "").strip(),(body.get("real_user") or "").strip(),int(body.get("mirror_account") or 0),(body.get("dest_group") or "").strip()))
                c.commit(); self.sendj(200,{"ok":True,"id":c.execute("SELECT last_insert_rowid()").fetchone()[0]})
            except Exception as e:
                self.sendj(400,{"detail":str(e)})
            c.close(); return
        if _p.startswith("/api/identities/") and _p.endswith("/delete"):
            c=sqlite3.connect("/var/lib/tgchat/tgchat.db")
            pk=int(_p.strip("/").split("/")[2]); c.execute("DELETE FROM identity_bindings WHERE id=?",(pk,)); c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        n=int(self.headers.get("Content-Length") or 0)
        body=json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        p=self.path.split("?")[0].rstrip("/")
        c=sqlite3.connect(DB)
        if p=="/api/apis":
            c.execute("INSERT INTO api_keys(name,api_id,api_hash) VALUES(?,?,?)",(body.get("name") or body.get("api_id"), body.get("api_id"), body.get("api_hash"))); c.commit(); self.sendj(200,{"ok":True})
        elif p=="/api/apis/batch":
            nadd=0
            for line in (body.get("text") or "").splitlines():
                line=line.strip()
                if not line or line.startswith("#"): continue
                import re
                m=re.match(r"(\d+)[-:\s]+([0-9a-fA-F]{32})\s*$", line)
                if m:
                    aid,ah=m.group(1),m.group(2)
                else:
                    parts=line.replace(":"," ").replace("-"," ",1).split()
                    if len(parts)<2: continue
                    aid,ah=parts[0],parts[1]
                c.execute("INSERT INTO api_keys(name,api_id,api_hash) VALUES(?,?,?)",(aid,aid,ah)); nadd+=1
            c.commit(); self.sendj(200,{"added":nadd})
        elif p=="/api/ips":
            c.execute("INSERT INTO ips(name,host,port,username,password,line) VALUES(?,?,?,?,?,?)",
                      (body.get("name") or body.get("host"), body.get("host"), int(body.get("port") or 0), body.get("username",""), body.get("password",""), body.get("line") or "default"))
            c.commit(); self.sendj(200,{"ok":True})
        elif p=="/api/ips/batch":
            nadd=0; line=body.get("line") or "default"
            for raw in (body.get("text") or "").splitlines():
                s=raw.strip()
                if not s or s.startswith("#"): continue
                parts=s.split(":")
                if len(parts)<2: continue
                host,port=parts[0],int(parts[1]); user=parts[2] if len(parts)>2 else ""; pw=parts[3] if len(parts)>3 else ""
                c.execute("INSERT INTO ips(name,host,port,username,password,line) VALUES(?,?,?,?,?,?)",(f"{line}-{host}-{port}",host,port,user,pw,line)); nadd+=1
            c.commit(); self.sendj(200,{"added":nadd})
        elif p=="/api/accounts":
            api=c.execute("SELECT id FROM api_keys WHERE account_id IS NULL ORDER BY id LIMIT 1").fetchone()
            if not api:
                self.sendj(400,{"detail":"API 池没有空闲项"}); c.close(); return
            ip=body.get("ip_id") or None
            if ip:
                c.execute("UPDATE accounts SET ip_id=NULL WHERE ip_id=?",(ip,))
                c.execute("UPDATE ips SET account_id=NULL WHERE id=?",(ip,))
            cur=c.execute("INSERT INTO accounts(display_name,phone,role,status,api_id,ip_id) VALUES(?,?,?,?,?,?)",
                          (body.get("display_name") or "未命名", body.get("phone",""), body.get("role") or "MIRROR","OFFLINE", api[0], ip))
            c.execute("UPDATE api_keys SET account_id=? WHERE id=?",(cur.lastrowid, api[0]))
            if ip: c.execute("UPDATE ips SET account_id=? WHERE id=?",(cur.lastrowid, ip))
            c.commit(); self.sendj(200,{"id":cur.lastrowid,"api_id":api[0],"ip_id":ip})

        elif p.startswith("/api/accounts/") and p.endswith("/send_code"):
            aid=int(p.split("/")[3])
            acc=c.execute("SELECT * FROM accounts WHERE id=?",(aid,)).fetchone()
            if not acc: self.sendj(404,{"detail":"账号不存在"}); c.close(); return
            api=c.execute("SELECT * FROM api_keys WHERE id=?",(acc[5] if False else acc["api_id"] if hasattr(acc,"keys") else acc[5],)).fetchone() if False else None
            row=c.execute("SELECT a.id,a.phone,a.display_name,a.api_id,k.api_id as tid,k.api_hash FROM accounts a LEFT JOIN api_keys k ON k.id=a.api_id WHERE a.id=?",(aid,)).fetchone()
            if not row or not row[4]:
                self.sendj(400,{"detail":"该号未分配 API"}); c.close(); return
            phone=body.get("phone") or row[1] or row[2]
            try:
                import otp
                res=otp.send_code(row[4], row[5], phone, aid)
                self.sendj(200,res)
            except Exception as e:
                self.sendj(400,{"detail":str(e)})
            c.close(); return
        elif p.startswith("/api/accounts/") and p.endswith("/sign_in"):
            aid=int(p.split("/")[3])
            try:
                import otp
                res=otp.sign_in(aid, body.get("code") or "", body.get("password") or "")
                if res.get("ok"):
                    c.execute("UPDATE accounts SET status=? WHERE id=?",("ONLINE",aid)); c.commit()
                self.sendj(200,res)
            except Exception as e:
                self.sendj(400,{"detail":str(e)})
            c.close(); return


        elif p.startswith("/api/accounts/") and p.endswith("/delete"):
            aid=int(p.split("/")[3])
            acc=c.execute("SELECT api_id,ip_id FROM accounts WHERE id=?",(aid,)).fetchone()
            if acc:
                if acc[0]: c.execute("UPDATE api_keys SET account_id=NULL WHERE id=?",(acc[0],))
                if acc[1]: c.execute("UPDATE ips SET account_id=NULL WHERE id=?",(acc[1],))
                c.execute("DELETE FROM accounts WHERE id=?",(aid,))
                c.commit()
            self.sendj(200,{"ok":True}); c.close(); return
        elif p.startswith("/api/apis/") and p.endswith("/delete"):
            pk=int(p.split("/")[3])
            c.execute("UPDATE accounts SET api_id=NULL WHERE api_id=?",(pk,))
            c.execute("DELETE FROM api_keys WHERE id=?",(pk,))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        elif p.startswith("/api/ips/") and p.endswith("/delete"):
            pk=int(p.split("/")[3])
            c.execute("UPDATE accounts SET ip_id=NULL WHERE ip_id=?",(pk,))
            c.execute("DELETE FROM ips WHERE id=?",(pk,))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return


        elif p.startswith("/api/accounts/") and p.endswith("/set_ip"):
            aid=int(p.split("/")[3])
            ip=body.get("ip_id") or None
            c.execute("UPDATE accounts SET ip_id=? WHERE id=?",(ip, aid))
            if ip:
                c.execute("UPDATE ips SET account_id=? WHERE id=? AND (account_id IS NULL OR account_id=?)",(aid,ip,aid))
            c.commit(); self.sendj(200,{"ok":True,"ip_id":ip}); c.close(); return


        elif p=="/api/binds":
            c.execute("CREATE TABLE IF NOT EXISTS binds(id INTEGER PRIMARY KEY AUTOINCREMENT,src_account INTEGER,src_chat TEXT,dst_account INTEGER,dst_chat TEXT,enabled INTEGER DEFAULT 1)")
            c.execute("INSERT INTO binds(src_account,src_chat,dst_account,dst_chat) VALUES(?,?,?,?)",
                      (body.get("src_account"), str(body.get("src_chat") or ""), body.get("dst_account"), str(body.get("dst_chat") or "")))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return
        elif p=="/api/keywords":
            c.execute("CREATE TABLE IF NOT EXISTS keywords(id INTEGER PRIMARY KEY AUTOINCREMENT,src TEXT,dst TEXT,enabled INTEGER DEFAULT 1)")
            c.execute("INSERT INTO keywords(src,dst) VALUES(?,?)",(body.get("src") or "", body.get("dst") or ""))
            c.commit(); self.sendj(200,{"ok":True}); c.close(); return


        elif p.startswith("/api/binds/") and p.endswith("/delete"):
            pk=int(p.split("/")[3])
            c.execute("DELETE FROM binds WHERE id=?",(pk,)); c.commit()
            self.sendj(200,{"ok":True}); c.close(); return

        else:
            self.sendj(404,{"detail":"Not Found"})
        c.close()

init()
print("LISTEN 127.0.0.1:8010", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8010), H).serve_forever()
