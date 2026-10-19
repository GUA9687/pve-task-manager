"""Third layout: 1080p overview, side-by-side GPUs, dense CPU small multiples."""
import copy,json,pathlib,re,runpy
ROOT=pathlib.Path(__file__).parent
g=runpy.run_path(str(ROOT/'build_compact.py'))
base=g['g'];panel,dash=base['panel'],base['dash'];OUT=ROOT/'dashboards'
COLORS={'pve':'#5794F2','ubuntu':'#73BF69','windows':'#FF9830','fnos':'#B877D9'}
NAMES={'pve':'PVE','ubuntu':'Ubuntu','windows':'Windows','fnos':'飞牛'}

def ov(p,name,props):
    p['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':name},'properties':[{'id':k,'value':v} for k,v in props.items()]})
def stat(title,series,x,y,w=24,h=2):
    p=panel(title,[(e,n) for n,e,u,c in series],x,y,w=w,h=h)
    p['options'].update(text={'titleSize':12,'valueSize':20},textMode='auto',orientation='auto',wideLayout=False)
    for n,e,u,c in series:ov(p,n,{'unit':u,'color':{'mode':'fixed','fixedColor':c}})
    return p
def chart(title,series,x,y,w=6,h=4,unit='percent'):
    p=panel(title,series,x,y,w=w,h=h,typ='timeseries',unit=unit)
    p['maxDataPoints']=240
    p['fieldConfig']['defaults']['color']={'mode':'palette-classic'}
    p['fieldConfig']['defaults']['custom'].update(lineInterpolation='linear',fillOpacity=5,axisBorderShow=False,axisLabel='',axisWidth=70)
    p['options']['legend']={'showLegend':True,'displayMode':'list','placement':'bottom'}
    for machine,color in COLORS.items():
        ov(p,machine,{'displayName':NAMES[machine],'color':{'mode':'fixed','fixedColor':color}})
    return p
def save(d):
    for i,p in enumerate(d['panels']):p['id']=i+1
    d['version']=1
    (OUT/('home.json' if d['uid']=='pve-home' else d['uid']+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def link(p,url):p['links']=[{'title':'详细信息','url':url,'targetBlank':False}]

# One consolidated host strip. Header is omitted to give labels and values their own space.
freq=g['freq'];temp=g['temp']
ps=[stat('',[
 ('PVE CPU','lab:cpu_usage_percent{machine="pve"}','percent','#5794F2'),
 ('工作频率',freq,'hertz','#5794F2'),
 ('内存已用','lab:memory_used_bytes{machine="pve"}','bytes','#B877D9'),
 ('内存占比','lab:memory_used_percent{machine="pve"}','percent','#B877D9'),
 ('CPU 功耗','lab_cpu_package_power_watts'+base['cpu_fresh'],'watt','#FFB357'),
 ('GPU 功耗','sum(lab_gpu_power_watts'+base['gpu_fresh']+')','watt','#56D4C0'),
 ('CPU 温度',temp,'celsius','#FF9830'),
 ('磁盘读取','lab:disk_read_bytes_per_second{machine="pve"}','Bps','#73BF69'),
 ('磁盘写入','lab:disk_write_bytes_per_second{machine="pve"}','Bps','#73BF69'),
 ('网络接收','lab:network_receive_bytes_per_second{machine="pve"}','Bps','#FF9830'),
 ('网络发送','lab:network_transmit_bytes_per_second{machine="pve"}','Bps','#FF9830')],0,0)]
ov(ps[0],'工作频率',{'decimals':3})
for n,dest in [('PVE CPU','cpu'),('工作频率','cpu'),('内存已用','memory'),('内存占比','memory'),('CPU 功耗','cpu'),('GPU 功耗','gpu'),('CPU 温度','sensors'),('磁盘读取','disk'),('磁盘写入','disk'),('网络接收','network'),('网络发送','network')]:
    ov(ps[0],n,{'links':[{'title':'详细信息','url':f'/d/pve-{dest}?var-machine=pve','targetBlank':False}]})
for i in range(2):
    e=lambda key:f'lab_gpu_{key}{{gpu="{i}"}}'+base['gpu_fresh']
    p=stat('',[(f'GPU {i} · 使用率',e('utilization_percent'),'percent','#56D4C0'),('显存已用',e('memory_used_bytes'),'bytes','#B877D9'),('温度',e('temperature_celsius'),'celsius','#FF9830'),('功耗',e('power_watts'),'watt','#FFB357'),('核心频率',e('clock_hertz'),'hertz','#5794F2'),('风扇',e('fan_percent'),'percent','#56D4C0')],i*12,2,w=12)
    p['fieldConfig']['defaults']['links']=[{'title':'GPU 详情','url':'/d/pve-gpu','targetBlank':False}];ps.append(p)
    p=chart(f'GPU {i} · 使用率 / 显存占比',[(e('utilization_percent'),'GPU'),(f'100 * lab_gpu_memory_used_bytes{{gpu="{i}"}} / lab_gpu_memory_total_bytes{{gpu="{i}"}}'+base['gpu_fresh'],'显存')],i*12,4,w=6)
    ov(p,'GPU',{'color':{'mode':'fixed','fixedColor':'#56D4C0'}});ov(p,'显存',{'color':{'mode':'fixed','fixedColor':'#B877D9'}});link(p,'/d/pve-gpu');ps.append(p)
    p=chart(f'GPU {i} · 功耗 / 温度',[(e('power_watts'),'功耗'),(e('temperature_celsius'),'温度')],i*12+6,4,w=6,unit='watt')
    ov(p,'温度',{'unit':'celsius','custom.axisPlacement':'right','color':{'mode':'fixed','fixedColor':'#FF9830'}});ov(p,'功耗',{'color':{'mode':'fixed','fixedColor':'#5794F2'}});link(p,'/d/pve-gpu');ps.append(p)

# One compact VM table, with units and links per column.
cols=[('CPU','cpu_usage_percent','percent','cpu'),('内存已用','memory_used_bytes','bytes','memory'),('内存占比','memory_used_percent','percent','memory'),('磁盘读','disk_read_bytes_per_second','Bps','disk'),('磁盘写','disk_write_bytes_per_second','Bps','disk'),('网络收','network_receive_bytes_per_second','Bps','network'),('网络发','network_transmit_bytes_per_second','Bps','network')]
expr=' or '.join(f'label_replace(lab:{key}{{machine=~"ubuntu|windows|fnos"}},"item","{name}","machine",".*")' for name,key,unit,page in cols)
p=panel('虚拟机 · 内部资源使用（fnos = 飞牛）',expr,0,8,w=24,h=5,typ='table')
p['targets'][0]['format']='table'
p['transformations']=[{'id':'groupingToMatrix','options':{'columnField':'item','rowField':'machine','valueField':'Value'}},{'id':'organize','options':{'indexByName':{'machine\\item':0,**{c[0]:i+1 for i,c in enumerate(cols)}},'renameByName':{'machine\\item':'机器'}}}]
p['options']={'showHeader':True,'cellHeight':'sm','footer':{'show':False}}
p['fieldConfig']['defaults']['custom']={'align':'left','cellOptions':{'type':'auto'},'minWidth':80}
ov(p,'机器',{'custom.width':150})
for name,key,unit,page in cols:
    ov(p,name,{'unit':unit,'links':[{'title':'详细信息','url':f'/d/pve-{page}?var-machine=${{__data.fields["机器"]}}','targetBlank':False}]})
ps.append(p)
for i,(title,key,unit,dest) in enumerate([('CPU · 四机趋势','cpu_usage_percent','percent','cpu'),('内存 · 四机占比','memory_used_percent','percent','memory'),('磁盘 · 读写总吞吐','disk_read_bytes_per_second','Bps','disk'),('网络 · 收发总吞吐','network_receive_bytes_per_second','Bps','network')]):
    ex='lab:'+key
    if dest=='disk':ex+=' + lab:disk_write_bytes_per_second'
    if dest=='network':ex+=' + lab:network_transmit_bytes_per_second'
    p=chart(title,[(ex,'{{machine}}')],i*6,13,unit=unit);link(p,'/d/pve-'+dest+'?var-machine=pve');ps.append(p)
ps.append(chart('CPU · 工作频率',[(freq,'工作频率')],0,17,unit='hertz'))
ps.append(chart('CPU · 封装功耗',[('lab_cpu_package_power_watts'+base['cpu_fresh'],'CPU')],6,17,unit='watt'))
ps.append(chart('CPU · 最高温度',[(temp,'最高温度')],12,17,unit='celsius'))
ps.append(stat('采集 · 24 小时分钟历史',[('在线台数','sum(up{job=~"linux|windows"})','short','#73BF69'),('实时周期','lab_monitor_scrape_interval_seconds','s','#5794F2'),('历史占用','lab_monitor_history_disk_bytes','bytes','#B877D9')],18,17,w=6,h=4))
dash('pve-home','PVE · 实时监控大屏',ps)

# CPU: common scales, 96 live bars, 12 columns of small charts.
d=json.loads((OUT/'pve-cpu.json').read_text(encoding='utf-8'));old=d['panels'];rep=copy.deepcopy(old[-1])
cp=[stat('',[('CPU 使用率','lab:cpu_usage_percent{machine="$machine"}','percent','#5794F2'),('逻辑 CPU','lab:cpu_count{machine="$machine"}','short','#5794F2'),('工作频率','lab_cpu_busy_frequency_hertz{machine="$machine",cpu=""}'+base['cpu_fresh'],'hertz','#5794F2'),('CPU 功耗','lab_cpu_package_power_watts{machine="$machine"}'+base['cpu_fresh'],'watt','#FFB357')],0,0,w=12)]
ov(cp[0],'逻辑 CPU',{'decimals':0});ov(cp[0],'工作频率',{'decimals':3})
p=chart('CPU 总利用率',[('lab:cpu_usage_percent{machine="$machine"}','CPU')],12,0,w=12,h=2);p['options']['legend']['showLegend']=False;p['fieldConfig']['defaults']['custom']['axisPlacement']='hidden';cp.append(p)
p=panel('逐核实时负载｜下方曲线统一量程：蓝色 0–100% · 橙色 0–4 GHz；悬停看数值','lab:cpu_core_usage_percent{machine="$machine"}',0,2,w=24,h=3,typ='bargauge',unit='percent',legend='{{cpu}}')
p['options'].update(orientation='vertical',displayMode='basic',valueMode='hidden',text={'titleSize':9,'valueSize':9},minVizWidth=10,showUnfilled=True)
cp.append(p)
rep['gridPos']={'x':0,'y':5,'w':2,'h':2};rep['maxPerRow']=12;rep['maxDataPoints']=120
rep['fieldConfig']['defaults']['custom'].update(axisPlacement='hidden',axisLabel='',axisBorderShow=False,axisGridShow=False,fillOpacity=4,lineInterpolation='linear')
for override in rep['fieldConfig']['overrides']:
    for prop in override['properties']:
        if prop['id']=='custom.axisPlacement':prop['value']='hidden'
rep['options']['legend']={'showLegend':False};rep['options']['tooltip']={'mode':'multi','sort':'none'}
# Fetch every core once; repeated panels reuse the same result locally.
for i,t in enumerate(rep['targets']):
    shared=copy.deepcopy(t)
    shared['expr']=shared['expr'].replace(',cpu="$cpu"',',cpu!=""')
    shared['legendFormat']=('利用率' if i==0 else '工作频率')+' {{cpu}}'
    shared['refId']=chr(66+i)
    cp[1]['targets'].append(shared)
cp[1]['maxDataPoints']=120
cp[1]['transformations']=[{'id':'filterFieldsByName','options':{'include':{'pattern':'^(Time|CPU)$'}}}]
rep['datasource']={'type':'datasource','uid':'-- Dashboard --'}
rep['targets']=[{'refId':'A','datasource':rep['datasource'],'panelId':2,'withTransforms':False}]
rep['transformations']=[{'id':'filterFieldsByName','options':{'include':{'pattern':'^(Time|(利用率|工作频率) ${cpu:regex})$'}}}]
rep['fieldConfig']['overrides'][0]['matcher']={'id':'byRegexp','options':'/^工作频率 /'}
cp.append(rep);d['panels']=cp;d['description']='小图共用顶部时间范围和固定量程，隐藏重复坐标轴与图例。虚拟机无可信物理频率。短期趋势使用实时缓存，超过30分钟使用每分钟历史。';save(d)

# GPU detail: same vertical positions for the two cards.
d=json.loads((OUT/'pve-gpu.json').read_text(encoding='utf-8'));old=d['panels'];gp=[]
for i in range(2):
    e=lambda key:f'lab_gpu_{key}{{gpu="{i}"}}'+base['gpu_fresh']
    entries=[(f'GPU {i} · 使用率','utilization_percent','percent','#56D4C0'),('显存已用','memory_used_bytes','bytes','#B877D9'),('温度','temperature_celsius','celsius','#FF9830'),('功耗','power_watts','watt','#FFB357'),('核心频率','clock_hertz','hertz','#5794F2'),('显存频率','memory_clock_hertz','hertz','#5794F2'),('风扇','fan_percent','percent','#56D4C0'),('功率上限','power_limit_watts','watt','#FFB357')]
    gp.append(stat('',[(n,e(k),u,c) for n,k,u,c in entries],i*12,0,w=12,h=3))
    for title,series,y,u in [('使用率 / 显存控制器',[(e('utilization_percent'),'GPU'),(e('memory_utilization_percent'),'显存控制器')],3,'percent'),('显存使用',[(e('memory_used_bytes'),'已用'),(e('memory_total_bytes'),'总量')],7,'bytes'),('功耗 / 温度',[(e('power_watts'),'功耗'),(e('temperature_celsius'),'温度')],11,'watt'),('核心 / 显存频率',[(e('clock_hertz'),'核心'),(e('memory_clock_hertz'),'显存')],15,'hertz')]:
        p=chart(f'GPU {i} · '+title,series,i*12,y,w=12,h=4,unit=u)
        if u=='watt':ov(p,'温度',{'unit':'celsius','custom.axisPlacement':'right','color':{'mode':'fixed','fixedColor':'#FF9830'}})
        gp.append(p)
d['panels']=gp;d['description']='两张GPU左右对照。功耗为驱动报告的实际功耗，功率上限单列；显存占用不等于计算利用率。';save(d)

# Compact the remaining detail dashboards; retain the original metric definitions.
layouts={
 'pve-memory':[(0,0,4,2),(4,0,4,2),(8,0,4,2),(12,0,4,2),(0,2,12,6),(16,0,4,2),(20,0,4,2),(12,2,12,6)],
 'pve-network':[(0,0,12,2),(12,0,12,2),(0,2,12,6),(12,2,12,6),(0,8,12,4),(12,8,12,4)],
 'pve-disk':[(0,0,12,2),(12,0,12,2),(0,2,6,5),(6,2,6,5),(12,2,6,5),(18,2,6,5),(0,7,8,5),(8,7,8,5),(16,7,8,5),(0,12,8,5),(8,12,16,5)],
 'pve-sensors':[(0,0,12,6),(12,0,12,6),(0,6,12,6),(12,6,12,6),(0,12,12,3),(12,12,12,3)]}
for uid,positions in layouts.items():
    d=json.loads((OUT/(uid+'.json')).read_text(encoding='utf-8'));note=d['panels'][0]['options']['content'];data=d['panels'][1:]
    assert len(data)==len(positions),(uid,len(data),len(positions))
    for p,(x,y,w,h) in zip(data,positions):
        p['gridPos']={'x':x,'y':y,'w':w,'h':h}
        if p['type']=='stat':p['options'].update(text={'titleSize':12,'valueSize':20},orientation='auto',textMode='auto')
        if p['type']=='timeseries':
            p['maxDataPoints']=240;p['options']['legend']={'showLegend':True,'displayMode':'list','placement':'bottom'}
            p['fieldConfig']['defaults']['custom'].update(fillOpacity=5,lineInterpolation='linear')
        if p['type']=='bargauge':p['options'].update(text={'titleSize':10,'valueSize':11},minVizHeight=12)
    d['panels']=data;d['description']=note;save(d)

# Refresh the allowlist for added charts without changing storage or cadence.
expressions=[t['expr'] for f in OUT.glob('*.json') for p in json.loads(f.read_text(encoding='utf-8'))['panels'] for t in p.get('targets',[]) if 'expr' in t]
expressions += [r['expr'] for group in json.loads((OUT/'rules.yml').read_text(encoding='utf-8'))['groups'] for r in group['rules']]
names=set(json.loads((ROOT/'metric-allowlist.json').read_text(encoding='utf-8')))
names.update(re.findall(r'\b(?:node_|windows_|lab_)[a-zA-Z0-9_]+',' '.join(expressions)))
(ROOT/'metric-allowlist.json').write_text(json.dumps(sorted(names),indent=2))
print('Dense dashboards generated; overview',len(ps),'panels; CPU 12 columns.')
