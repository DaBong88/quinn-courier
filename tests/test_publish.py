import json, os, subprocess, sys, threading, shutil, tempfile, hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
HERE=os.path.dirname(os.path.abspath(__file__)); SRC=os.path.dirname(HERE)
LOG=[]; MODE={"ig_publish":200}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,code,obj):
        b=json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def _body(self):
        n=int(self.headers.get("Content-Length",0)); return self.rfile.read(n)
    def do_POST(self):
        b=self._body(); p=self.path; LOG.append(("POST",p,self.headers.get("Authorization","")[:6]))
        if p.endswith("/media_publish"):
            return self._send(MODE["ig_publish"],{"id":"IGPOST1"} if MODE["ig_publish"]==200 else {"error":"x"})
        if p.endswith("/media"): return self._send(200,{"id":"CONT1"})
        if p=="/2/media/upload/initialize": return self._send(200,{"data":{"id":"M1"}})
        if p.endswith("/append"): return self._send(200,{"data":{"expires_at":1}})
        if p.endswith("/finalize"): return self._send(200,{"data":{"id":"M1"}})
        if p=="/2/tweets":
            assert self.headers["Authorization"].startswith("OAuth ")
            d=json.loads(b); LOG.append(("TWEET",d)); return self._send(201,{"data":{"id":"T1","text":d["text"]}})
        self._send(404,{})
    def do_GET(self):
        LOG.append(("GET",self.path))
        if "status_code" in self.path: return self._send(200,{"status_code":"FINISHED"})
        if "permalink" in self.path: return self._send(200,{"permalink":"https://instagram.com/p/abc"})
        self._send(404,{})
srv=HTTPServer(("127.0.0.1",0),H); port=srv.server_port
threading.Thread(target=srv.serve_forever,daemon=True).start()
def h(j): return hashlib.sha256("|".join([j["caption"],j.get("mediaId",""),j["account"],j.get("scheduledFor","")]).encode()).hexdigest()
def job(id,acc,**kw):
    j={"id":id,"account":acc,"stage":"approved","caption":"Hello from Quinn. I'm an AI.","mediaId":"m1","scheduledFor":"2020-01-01T00:00:00Z","mediaUrl":"https://example.com/a.jpg","mediaPath":"media/test.jpg"}
    j.update(kw); j["approvedHash"]=kw.get("approvedHash",h(j)); return j
def run(jobs,paused=False,ledger=None,dry=False):
    d=tempfile.mkdtemp(); shutil.copytree(SRC,d,dirs_exist_ok=True,ignore=shutil.ignore_patterns(".git","tests"))
    json.dump(jobs,open(d+"/queue/jobs.json","w")); json.dump({"paused":paused},open(d+"/control.json","w")); json.dump(ledger or {},open(d+"/state/ledger.json","w")); json.dump({},open(d+"/queue/results.json","w"))
    e=dict(os.environ,IG_API_BASE=f"http://127.0.0.1:{port}/v25.0",X_API_BASE=f"http://127.0.0.1:{port}",IG_USER_ID="123",IG_ACCESS_TOKEN="fake",X_API_KEY="k",X_API_SECRET="s",X_ACCESS_TOKEN="t",X_ACCESS_SECRET="ts",IG_POLL_SLEEP="0",RETRY_SLEEP="0",DRY_RUN="1" if dry else "0")
    LOG.clear(); p=subprocess.run([sys.executable,d+"/publish.py"],env=e,capture_output=True,text=True)
    return p.returncode,json.load(open(d+"/queue/results.json")),json.load(open(d+"/state/ledger.json")),p.stdout
def t(name,cond): print(("PASS " if cond else "FAIL ")+name); assert cond,name
rc,r,l,o=run([job("a","quinn_ig")],paused=True); t("paused posts nothing",rc==0 and not LOG and not r)
rc,r,l,o=run([job("a","quinn_ig"),job("b","quinn_x")]); t("both publish",rc==0 and r["a"]["status"]=="published" and r["b"]["status"]=="published")
t("ig permalink",r["a"]["url"]=="https://instagram.com/p/abc"); t("x url",r["b"]["url"].endswith("/T1"))
t("x tweet has media",("TWEET",{"text":"Hello from Quinn. I'm an AI.","media":{"media_ids":["M1"]}}) in LOG)
rc,r,l,o=run([job("a","quinn_x")],ledger={"a":{"status":"published"}}); t("ledger blocks repeat",rc==0 and not LOG)
j=job("c","quinn_x"); j["caption"]="Edited after approval"
rc,r,l,o=run([j]); t("edited after approval blocked",rc==1 and r["c"]["status"]=="blocked" and not LOG)
rc,r,l,o=run([job("d","quinn_li")]); t("allowlist blocks",rc==1 and r["d"]["status"]=="blocked")
rc,r,l,o=run([job("e","quinn_x",scheduledFor="2099-01-01T00:00:00Z")]); t("future job waits",rc==0 and not LOG and not r)
rc,r,l,o=run([job("f","quinn_x",stage="awaiting")]); t("unapproved ignored",rc==0 and not LOG)
rc,r,l,o=run([job("g","quinn_x",caption="x"*281)]); t("x length enforced",rc==1 and r["g"]["status"]=="blocked")
rc,r,l,o=run([job("h","quinn_ig",mediaUrl="")]); t("ig needs media",rc==1)
MODE["ig_publish"]=500; rc,r,l,o=run([job("i","quinn_ig")]); MODE["ig_publish"]=200
t("publish 500 -> unknown, once",rc==1 and r["i"]["status"]=="unknown" and sum(1 for x in LOG if x[0]=="POST" and x[1].endswith("/media_publish"))==1 and "i" in l)
rc,r,l,o=run([job("j","quinn_x")],dry=True); t("dry run no calls",rc==0 and r["j"]["status"]=="dry_run_ok" and not LOG and not l)
print("ALL PASS")
