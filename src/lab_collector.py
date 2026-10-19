#!/usr/bin/env python3
"""Read-only hardware collectors, atomically exported via node_exporter textfiles."""
import csv, io, json, math, os, pathlib, re, subprocess, sys, threading, time, urllib.request

ROOT=pathlib.Path('/var/lib/node_exporter/textfile')
ROOT.mkdir(parents=True,exist_ok=True)

def run(args, timeout=25):
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:300] or str(r.returncode))
    return r.stdout

def metric(metric_name,value,**labels):
    value=float(value)
    if not math.isfinite(value): return ''
    tag=','.join(k+'='+json.dumps(str(v),ensure_ascii=True) for k,v in labels.items())
    return metric_name+('{'+tag+'}' if tag else '')+' '+str(value)+'\n'

LIVE=False
LAST_MODE=0

def watch_mode():
    global LIVE,LAST_MODE
    config=json.loads(pathlib.Path('/etc/node_exporter/adaptive.json').read_text())
    while True:
        try:
            req=urllib.request.Request(config['url'],headers={'Authorization':'Bearer '+config['token']})
            with urllib.request.urlopen(req,timeout=2) as r:LIVE=bool(json.load(r)['active'])
            LAST_MODE=time.monotonic()
        except Exception:LIVE=False
        time.sleep(3)

def interval_for(name):
    live=LIVE and time.monotonic()-LAST_MODE < 10
    return {'cpu':1 if live else 60,'gpu':1 if live else 60,'inventory':15 if live else 60,'bmc':60,'smart':300}[name]

def worker(name,interval,fn):
    last=0
    while True:
        start=time.monotonic()
        try:
            content=fn();last=time.time();ok=1
        except Exception as e:
            print(name+': '+str(e),flush=True);content='';ok=0
        content+=metric('lab_collector_success',ok,collector=name)+metric('lab_collector_last_success_seconds',last,collector=name)
        tmp=ROOT/(name+'.tmp');tmp.write_text(content);tmp.replace(ROOT/(name+'.prom'))
        while time.monotonic()-start < interval_for(name):time.sleep(0.15)

def cpu():
    text=run(['/usr/sbin/turbostat','--quiet','--interval','0.5','--num_iterations','1','--show','CPU,Core,Busy%,Bzy_MHz,Avg_MHz,PkgWatt'],12)
    lines=text.strip().splitlines(); headers=lines[0].split(); out=''
    for line in lines[1:]:
        r=dict(zip(headers,line.split()))
        if r.get('CPU')=='-':
            out+=metric('lab_cpu_package_power_watts',r['PkgWatt'])
            out+=metric('lab_cpu_busy_frequency_hertz',float(r['Bzy_MHz'])*1e6)
        elif r.get('CPU','').isdigit():
            tags={'cpu':r['CPU'],'core':r['Core']}
            out+=metric('lab_cpu_busy_percent',r['Busy%'],**tags)
            out+=metric('lab_cpu_busy_frequency_hertz',float(r['Bzy_MHz'])*1e6,**tags)
            out+=metric('lab_cpu_average_frequency_hertz',float(r['Avg_MHz'])*1e6,**tags)
            out+=metric('lab_cpu_topology',1,**tags)
    if 'lab_cpu_package_power_watts' not in out: raise ValueError('No CPU package sample')
    return out

def inventory():
    rows=json.loads(run(['pvesh','get','/cluster/resources','--type','vm','--output-format','json'],20));out=''
    names={int(k):v for k,v in json.loads(pathlib.Path('/etc/node_exporter/adaptive.json').read_text())['vm_map'].items()}
    for r in rows:
        if r.get('vmid') not in names:continue
        tags={'guest':names[r['vmid']],'vmid':r['vmid'],'name':r.get('name','')}
        out+=metric('lab_vm_running',r.get('status')=='running',**tags)
        for field,name in [('maxcpu','vcpus'),('maxmem','configured_memory_bytes'),('memhost','host_memory_bytes'),('uptime','uptime_seconds')]:
            if field in r:out+=metric('lab_vm_'+name,r[field],**tags)
        if r.get('status')=='running' and 'cpu' in r:out+=metric('lab_vm_cpu_cores',r['cpu']*r['maxcpu'],**tags)
    return out

def bmc():
    out=''
    for line in run(['/usr/bin/ipmitool','sensor','list'],45).splitlines():
        p=[s.strip() for s in line.split('|')]
        if len(p)<4:continue
        try:value=float(p[1])
        except ValueError:continue
        typ={'degrees C':'temperature_celsius','RPM':'fan_rpm','Volts':'voltage_volts'}.get(p[2])
        if typ:out+=metric('lab_bmc_'+typ,value,sensor=p[0])
    if not out:raise ValueError('No valid BMC sensors')
    return out

def gpu():
    fields=['index','name','uuid','memory.total','memory.used','utilization.gpu','utilization.memory','temperature.gpu','power.draw','power.limit','clocks.current.graphics','clocks.current.memory','fan.speed']
    txt=run(['nvidia-smi','--query-gpu='+','.join(fields),'--format=csv,noheader,nounits'],15);out=''
    mapping={'memory.total':('memory_total_bytes',1048576),'memory.used':('memory_used_bytes',1048576),'utilization.gpu':('utilization_percent',1),'utilization.memory':('memory_utilization_percent',1),'temperature.gpu':('temperature_celsius',1),'power.draw':('power_watts',1),'power.limit':('power_limit_watts',1),'clocks.current.graphics':('clock_hertz',1e6),'clocks.current.memory':('memory_clock_hertz',1e6),'fan.speed':('fan_percent',1)}
    for row in csv.reader(io.StringIO(txt)):
        r=dict(zip(fields,[x.strip() for x in row]));tags={'gpu':r['index'],'model':r['name'],'uuid':r['uuid']}
        out+=metric('lab_gpu_info',1,**tags)
        for field,(name,mult) in mapping.items():
            try:out+=metric('lab_gpu_'+name,float(r[field])*mult,**tags)
            except (ValueError,KeyError):pass
    if not out:raise ValueError('No GPU sample')
    return out

def smart():
    out=''
    for path in sorted(pathlib.Path('/sys/block').iterdir()):
        disk=path.name
        if not re.fullmatch(r'(sd[a-z]+|nvme\d+n\d+)',disk):continue
        modelpath=path/'device/model'
        if modelpath.exists() and 'QEMU' in modelpath.read_text():continue
        p=subprocess.run(['/usr/sbin/smartctl','-n','standby','-a','-j','/dev/'+disk],capture_output=True,text=True,timeout=20)
        try:r=json.loads(p.stdout)
        except ValueError:continue
        tags={'disk':disk,'model':r.get('model_name',r.get('model_family','unknown'))}
        if 'temperature' in r and 'current' in r['temperature']:out+=metric('lab_disk_temperature_celsius',r['temperature']['current'],**tags)
        if 'smart_status' in r:out+=metric('lab_disk_smart_passed',r['smart_status']['passed'],**tags)
        if 'power_on_time' in r:out+=metric('lab_disk_power_on_hours',r['power_on_time'].get('hours',0),**tags)
        nv=r.get('nvme_smart_health_information_log',{})
        for key in ['percentage_used','media_errors','available_spare','unsafe_shutdowns']:
            if key in nv:out+=metric('lab_disk_'+key,nv[key],**tags)
        for a in r.get('ata_smart_attributes',{}).get('table',[]):
            if a.get('id') in [5,187,197,198,199]:out+=metric('lab_disk_smart_attribute_raw',a['raw']['value'],attribute=a['name'],**tags)
    return out

if __name__=='__main__':
    mode=sys.argv[1]
    jobs={'pve':[('cpu',5,cpu),('inventory',15,inventory),('bmc',60,bmc),('smart',300,smart)],'ubuntu':[('gpu',5,gpu)],'fnos':[('smart',300,smart)]}[mode]
    threading.Thread(target=watch_mode,daemon=True).start()
    threads=[threading.Thread(target=worker,args=j) for j in jobs]
    for t in threads:t.start()
    for t in threads:t.join()
