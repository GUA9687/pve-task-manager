import runpy,json,pathlib,re
root=pathlib.Path(__file__).parent
g=runpy.run_path(str(root/'build_dashboards.py'))
panel,dash=g['panel'],g['dash']
ps=[]
def add(title,expr,x,y,w=4,h=2,unit='short',color='#5794F2',link=None,typ='stat'):
    p=panel(title,expr,x,y,w=w,h=h,unit=unit,color=color,link=link,typ=typ)
    if typ=='stat':p['options'].update(text={'titleSize':10,'valueSize':19},wideLayout=True,orientation='auto',textMode='value')
    if typ=='timeseries':
        p['options']['legend']={'showLegend':True,'displayMode':'list','placement':'bottom'}
        p['fieldConfig']['defaults']['custom'].update(fillOpacity=8,lineWidth=1)
    ps.append(p);return p
def override(p,name,unit,color=None):
    props=[{'id':'unit','value':unit}]
    if color:props.append({'id':'color','value':{'mode':'fixed','fixedColor':color}})
    p['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':name},'properties':props})

freq='lab_cpu_busy_frequency_hertz{machine="pve",cpu=""}'+g['cpu_fresh']
temp='max(node_hwmon_temp_celsius{machine="pve"} * on(machine,chip,instance,job) group_left(chip_name) node_hwmon_chip_names{machine="pve",chip_name="k10temp"})'
items=[('CPU 使用率','lab:cpu_usage_percent{machine="pve"}','percent','#5794F2','cpu'),('工作频率',freq,'hertz','#5794F2','cpu'),('内存已用','lab:memory_used_bytes{machine="pve"}','bytes','#B877D9','memory'),('CPU 功耗','lab_cpu_package_power_watts'+g['cpu_fresh'],'watt','#FFB357','cpu'),('GPU 总功耗','sum(lab_gpu_power_watts'+g['gpu_fresh']+')','watt','#56D4C0','gpu'),('CPU 温度',temp,'celsius','#FF9830','sensors')]
for i,(t,e,u,c,l) in enumerate(items):add(t,e,i*4,0,unit=u,color=c,link='/d/pve-'+l+'?var-machine=pve')
for gpu in range(2):
    e=lambda key:f'lab_gpu_{key}{{gpu="{gpu}"}}'+g['gpu_fresh']
    p=add(f'GPU {gpu} · 利用率 / 显存 / 温度 / 功耗',[(e('utilization_percent'),'利用率'),(e('memory_used_bytes'),'显存'),(e('temperature_celsius'),'温度'),(e('power_watts'),'功耗')],gpu*12,2,w=12,h=2,unit='percent',color='#56D4C0',link='/d/pve-gpu')
    override(p,'显存','bytes','#B877D9');override(p,'温度','celsius','#FF9830');override(p,'功耗','watt','#FFB357')
add('PVE · 磁盘读 / 写',[('lab:disk_read_bytes_per_second{machine="pve"}','读'),('lab:disk_write_bytes_per_second{machine="pve"}','写')],0,4,w=8,unit='Bps',color='#73BF69',link='/d/pve-disk?var-machine=pve')
add('PVE · 网络收 / 发',[('lab:network_receive_bytes_per_second{machine="pve"}','收'),('lab:network_transmit_bytes_per_second{machine="pve"}','发')],8,4,w=8,unit='Bps',color='#FF9830',link='/d/pve-network?var-machine=pve')
p=add('在线台数 / 实时周期 / 历史占用',[('sum(up{job=~"linux|windows"})','在线机器'),('lab_monitor_scrape_interval_seconds','实时周期'),('lab_monitor_history_disk_bytes','历史占用')],16,4,w=8)
override(p,'实时周期','s');override(p,'历史占用','bytes');p['fieldConfig']['defaults']['decimals']=0
for idx,(m,name) in enumerate([('ubuntu','Ubuntu'),('windows','Windows'),('fnos','飞牛')]):
    y=6+idx*2
    add(name+' · CPU',f'lab:cpu_usage_percent{{machine="{m}"}}',0,y,w=4,unit='percent',link=f'/d/pve-cpu?var-machine={m}')
    p=add(name+' · 内存 / 占比',[(f'lab:memory_used_bytes{{machine="{m}"}}','已用'),(f'lab:memory_used_percent{{machine="{m}"}}','使用率')],4,y,w=6,unit='bytes',color='#B877D9',link=f'/d/pve-memory?var-machine={m}')
    override(p,'使用率','percent')
    add(name+' · 磁盘读 / 写',[(f'lab:disk_read_bytes_per_second{{machine="{m}"}}','读'),(f'lab:disk_write_bytes_per_second{{machine="{m}"}}','写')],10,y,w=7,unit='Bps',color='#73BF69',link=f'/d/pve-disk?var-machine={m}')
    add(name+' · 网络收 / 发',[(f'lab:network_receive_bytes_per_second{{machine="{m}"}}','收'),(f'lab:network_transmit_bytes_per_second{{machine="{m}"}}','发')],17,y,w=7,unit='Bps',color='#FF9830',link=f'/d/pve-network?var-machine={m}')
for i,(title,key,unit,c) in enumerate([('CPU · 四机趋势','cpu_usage_percent','percent','#5794F2'),('内存 · 四机趋势','memory_used_percent','percent','#B877D9'),('网络接收 · 四机趋势','network_receive_bytes_per_second','Bps','#FF9830')]):
    p=add(title,[(f'lab:{key}', '{{machine}}')],i*8,12,w=8,h=4,typ='timeseries',unit=unit,color=c)
    p['fieldConfig']['defaults']['color']={'mode':'palette-classic'}
dash('pve-home','PVE · 实时监控大屏',ps)
# Keep only metrics actually used by the dashboards/rules, plus source freshness and health.
expressions=[]
for path in (root/'dashboards').glob('*.json'):
    d=json.loads(path.read_text(encoding='utf-8'))
    expressions += [t['expr'] for p in d['panels'] for t in p.get('targets',[])]
expressions += [r['expr'] for group in json.loads((root/'dashboards/rules.yml').read_text())['groups'] for r in group['rules']]
names=sorted(set(re.findall(r'\b(?:node_|windows_|lab_)[a-zA-Z0-9_]+',' '.join(expressions))))
names+=['node_disk_info','node_hwmon_chip_names','lab_collector_last_success_seconds','lab_collector_success','lab_monitor_active','lab_monitor_scrape_interval_seconds','lab_monitor_history_interval_seconds','lab_monitor_history_disk_bytes','lab_monitor_switch_ok']
(root/'metric-allowlist.json').write_text(json.dumps(sorted(set(names)),indent=2))
print('Compact overview:',len(ps),'panels; metric allowlist:',len(set(names)))

