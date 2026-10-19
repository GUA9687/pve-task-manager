import json,pathlib,urllib.request,urllib.parse
def query(e):
    with urllib.request.urlopen('http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':e}),timeout=15) as r:return json.load(r)
for e in ['up','count by(machine)(lab:cpu_core_usage_percent)','lab:cpu_usage_percent','lab:memory_used_bytes','lab:network_receive_bytes_per_second','lab_collector_success','lab_cpu_package_power_watts','lab_gpu_power_watts','count by(machine)(lab_disk_temperature_celsius)','count by(machine)(lab_disk_smart_passed)']:
    r=query(e); print(json.dumps({'query':e,'result':r.get('data',{}).get('result',[])},ensure_ascii=True))
errors=[];empty=[];tested=0
for f in pathlib.Path('/var/lib/grafana/dashboards').glob('*.json'):
    d=json.loads(f.read_text())
    for p in d['panels']:
        for t in p.get('targets',[]):
            if 'expr' not in t:continue
            for machine in (['pve','ubuntu','windows','fnos'] if '$machine' in t['expr'] else ['pve']):
                expr=t['expr'].replace('$machine',machine).replace('$cpu','0')
                try:
                    r=query(expr);tested+=1
                    if r.get('status')!='success':errors.append([f.name,p['title'],machine,r])
                    elif not r['data']['result']:empty.append([f.name,p['title'],machine])
                except Exception as e:errors.append([f.name,p['title'],machine,str(e)])
print(json.dumps({'tested':tested,'errors':errors,'empty':empty},ensure_ascii=True))
