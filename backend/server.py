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
            ip=body.get("ip_id")
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

        else:
            self.sendj(404,{"detail":"Not Found"})
        c.close()

init()
print("LISTEN 127.0.0.1:8010", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8010), H).serve_forever()
