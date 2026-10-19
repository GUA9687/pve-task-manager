#!/usr/bin/env python3
"""Local Grafana query router; persistent 60s history and adaptive RAM-only live data."""
import datetime, hmac, http.server, json, pathlib, subprocess, threading, time, urllib.parse, urllib.request, urllib.error

ROOT=pathlib.Path('/etc/pve-monitor')
SETTINGS=json.loads((ROOT/'adaptive.json').read_text())
LIVE=pathlib.Path('/etc/prometheus/live.yml')
lock=threading.Lock()
last_activity=0.0
mode=False
changed=0.0
last_error=''

def active():
    with lock:return time.monotonic()-last_activity < 60

def switch(wanted):
    global mode,changed,last_error
    with urllib.request.urlopen('http://127.0.0.1:9093/-/ready',timeout=2) as r:
        if r.status!=200:raise RuntimeError('Live backend not ready')
    conf=json.loads(LIVE.read_text())
    interval='1s' if wanted else '60s'
    conf['global'].update(scrape_interval=interval,evaluation_interval=interval,scrape_timeout='900ms' if wanted else '10s')
    temp=LIVE.with_suffix('.tmp')
    temp.write_text(json.dumps(conf,indent=2));temp.chmod(0o640)
    import shutil
    shutil.chown(temp,user='prometheus',group='prometheus')
    subprocess.run(['/usr/local/bin/promtool','check','config',str(temp)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=10)
    temp.replace(LIVE)
    subprocess.run(['/bin/systemctl','kill','-s','HUP','prometheus-live'],check=True,timeout=5)
    mode=wanted;changed=time.time();last_error=''
    print('Live sampling: '+interval,flush=True)

def control():
    global last_error
    first=True
    while True:
        wanted=active()
        if first or wanted!=mode:
            try:switch(wanted);first=False
            except Exception as e:last_error=type(e).__name__;print('Switch failed: '+str(e),flush=True)
        time.sleep(1)

def timestamp(raw,default):
    if not raw:return default
    try:return float(raw)
    except ValueError:
        try:return datetime.datetime.fromisoformat(raw.replace('Z','+00:00')).timestamp()
        except ValueError:return default

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def send(self,code,body,content_type='application/json'):
        self.send_response(code);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def handle_request(self):
        global last_activity
        path=urllib.parse.urlsplit(self.path)
        local=self.client_address[0] in ('127.0.0.1','::1')
        if path.path=='/mode':
            if not local and not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+SETTINGS['token']):
                self.send(401,b'{"error":"unauthorized"}');return
            self.send(200,json.dumps({'active':mode,'interval':1 if mode else 60,'history_interval':60,'grace_seconds':60,'changed':changed,'error':last_error}).encode());return
        if not local:self.send(403,b'{"error":"local proxy only"}');return
        if path.path=='/metrics':
            total=sum(p.stat().st_blocks*512 for p in pathlib.Path('/var/lib/prometheus').rglob('*') if p.is_file())
            text=f'lab_monitor_active {int(mode)}\nlab_monitor_scrape_interval_seconds {1 if mode else 60}\nlab_monitor_history_interval_seconds 60\nlab_monitor_history_disk_bytes {total}\nlab_monitor_switch_ok {int(not last_error)}\n'
            self.send(200,text.encode(),'text/plain; version=0.0.4');return
        if not path.path.startswith('/api/v1/'):
            self.send(404,b'{}');return
        length=int(self.headers.get('Content-Length','0'))
        if length>1048576:self.send(413,b'{}');return
        body=self.rfile.read(length) if length else None
        params=urllib.parse.parse_qs(path.query)
        if body:params.update(urllib.parse.parse_qs(body.decode()))
        now=time.time()
        if path.path in ('/api/v1/query','/api/v1/query_range'):
            with lock:last_activity=time.monotonic()
        # Up to 30 minutes uses fine-grained volatile data; longer or older windows use disk history.
        start=timestamp(params.get('start',[''])[0],now)
        end=timestamp(params.get('end',params.get('time',['']))[0],now)
        historical=start < now-1860 or end < now-1860
        port=9090 if historical else 9093
        url=f'http://127.0.0.1:{port}'+self.path
        req=urllib.request.Request(url,data=body,method=self.command,headers={'Content-Type':self.headers.get('Content-Type','application/x-www-form-urlencoded')})
        try:
            with urllib.request.urlopen(req,timeout=15) as r:self.send(r.status,r.read(),r.headers.get('Content-Type','application/json'))
        except urllib.error.HTTPError as e:self.send(e.code,e.read())
        except Exception:self.send(502,b'{"status":"error","error":"Monitoring backend unavailable"}')

if __name__=='__main__':
    threading.Thread(target=control,daemon=True).start()
    http.server.ThreadingHTTPServer(('0.0.0.0',9091),Handler).serve_forever()
