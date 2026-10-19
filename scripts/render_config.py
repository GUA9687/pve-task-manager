"""Render a private staging tree. Does not install or restart anything."""
import argparse,json,os,pathlib,re,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]

def render(inventory,output,env):
    names=['EXPORTER_PASSWORD','EXPORTER_PASSWORD_HASH','ADAPTIVE_TOKEN','GRAFANA_ADMIN_PASSWORD']
    values={k:env.get(k,'') for k in names}
    for k,v in values.items():
        if len(v)<20 or any(c in v for c in '\r\n') or 'REPLACE' in v:
            raise ValueError(k+' must be a private value of at least 20 characters without line breaks')
    if not re.fullmatch(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}',values['EXPORTER_PASSWORD_HASH']):
        raise ValueError('EXPORTER_PASSWORD_HASH must be a bcrypt hash of EXPORTER_PASSWORD')
    for hostname in [inventory['monitor_host'],*inventory['machines'].values()]:
        if not re.fullmatch(r'[A-Za-z0-9.-]+',hostname) or hostname.endswith('.invalid'):
            raise ValueError('Replace example hosts with real IPv4 addresses or DNS names')
    if set(inventory['machines'])!={'pve','ubuntu','windows','fnos'}:
        raise ValueError('This template requires pve, ubuntu, windows and fnos machine labels')
    if set(inventory['vm_map'].values())!={'ubuntu','windows','fnos'}:
        raise ValueError('vm_map must map the three VM IDs to ubuntu/windows/fnos')
    for vmid in inventory['vm_map']:int(vmid)
    output=pathlib.Path(output)
    if output.exists():raise ValueError('Output already exists; choose a new directory to preserve private config')
    output.mkdir(parents=True,mode=0o700)
    def write(path,value,private=False):
        p=output/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(value if isinstance(value,str) else json.dumps(value,indent=2),encoding='utf-8')
        if private:p.chmod(0o600)
    allow='|'.join(json.loads((ROOT/'src/metric-allowlist.json').read_text(encoding='utf-8')))
    for filename in ['prometheus.yml','live.yml']:
        conf=json.loads((ROOT/'config'/filename).read_text(encoding='utf-8'))
        for job in conf['scrape_configs']:
            if 'basic_auth' in job:job['basic_auth']['password']=values['EXPORTER_PASSWORD']
            for rule in job.get('metric_relabel_configs',[]):
                if rule.get('action')=='keep':rule['regex']=allow
            for item in job.get('static_configs',[]):
                machine=item['labels']['machine']
                if machine in inventory['machines']:
                    item['targets']=[inventory['machines'][machine]+(':'+str(9182 if machine=='windows' else 9100))]
        write('platform/etc/prometheus/'+filename,conf,True)
    write('platform/etc/prometheus/rules.yml',(ROOT/'dashboards/rules.yml').read_text(encoding='utf-8'))
    write('platform/etc/pve-monitor/adaptive.json',{'token':values['ADAPTIVE_TOKEN']},True)
    write('platform/etc/grafana/admin-password',values['GRAFANA_ADMIN_PASSWORD'],True)
    write('platform/etc/grafana/grafana.ini',(ROOT/'config/grafana.ini').read_text(encoding='utf-8'))
    write('platform/etc/systemd/journald.conf.d/monitor-budget.conf','[Journal]\nSystemMaxUse=8M\nSystemMaxFileSize=2M\nRuntimeMaxUse=8M\nRuntimeMaxFileSize=2M\n')
    for p in (ROOT/'config/systemd').glob('*.service'):
        write('platform/etc/systemd/system/'+p.name,p.read_text(encoding='utf-8'))
    for p in (ROOT/'config/provisioning').rglob('*.yml'):
        write('platform/etc/grafana/provisioning/'+str(p.relative_to(ROOT/'config/provisioning')),p.read_text(encoding='utf-8'))
    for p in (ROOT/'dashboards').glob('*.json'):
        write('platform/var/lib/grafana/dashboards/'+p.name,p.read_text(encoding='utf-8'))
    write('platform/usr/local/lib/adaptive_monitor.py',(ROOT/'src/adaptive_monitor.py').read_text(encoding='utf-8'))
    write('platform/usr/local/sbin/backup-monitor-config.py',(ROOT/'scripts/backup-monitor-config.py').read_text(encoding='utf-8'))
    for machine in ['pve','ubuntu','fnos']:
        config={'url':'http://'+inventory['monitor_host']+':9091/mode','token':values['ADAPTIVE_TOKEN']}
        if machine=='pve':config['vm_map']=inventory['vm_map']
        write(machine+'/etc/node_exporter/adaptive.json',config,True)
        write(machine+'/etc/node_exporter/web.yml',{'basic_auth_users':{'monitor':values['EXPORTER_PASSWORD_HASH']}},True)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',default='config/inventory.json')
    parser.add_argument('--output',default='build/deployment')
    args=parser.parse_args()
    result=render(json.loads(pathlib.Path(args.inventory).read_text(encoding='utf-8')),args.output,os.environ)
    print('Private staging files written to '+str(result)+'; no services were changed')

