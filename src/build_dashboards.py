import json, pathlib
OUT=pathlib.Path(__file__).parent/'dashboards'
OUT.mkdir(exist_ok=True)
DS={'type':'prometheus','uid':'pve-prom'}
MASK=' and on(machine) (up{job=~"linux|windows"} == 1)'
rules=[]
def record(name,expr):
    if name in ['cpu_usage_percent','cpu_core_usage_percent']:expr='clamp(('+expr+'),0,100)'
    rules.append({'record':'lab:'+name,'expr':'('+expr+')'+MASK})
record('cpu_usage_percent','100 * (1 - avg by(machine)(irate(node_cpu_seconds_total{mode="idle"}[5m]))) or 100 * (1 - avg by(machine)(irate(windows_cpu_time_total{mode="idle"}[5m])))')
record('cpu_core_usage_percent','100 * (1 - avg by(machine,cpu)(irate(node_cpu_seconds_total{mode="idle"}[5m]))) or label_replace(100 * (1 - avg by(machine,core)(irate(windows_cpu_time_total{mode="idle"}[5m]))), "cpu", "$1", "core", "(.*)")')
record('cpu_count','count by(machine)(node_cpu_seconds_total{mode="idle"}) or max by(machine)(windows_cpu_logical_processor)')
record('memory_total_bytes','max by(machine)(node_memory_MemTotal_bytes) or max by(machine)(windows_memory_physical_total_bytes)')
record('memory_available_bytes','max by(machine)(node_memory_MemAvailable_bytes) or max by(machine)(windows_memory_available_bytes)')
record('memory_used_bytes','max by(machine)(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) or max by(machine)(windows_memory_physical_total_bytes - windows_memory_available_bytes)')
record('memory_used_percent','100 * (1 - max by(machine)(node_memory_MemAvailable_bytes)/max by(machine)(node_memory_MemTotal_bytes)) or 100 * (1-max by(machine)(windows_memory_available_bytes)/max by(machine)(windows_memory_physical_total_bytes))')
record('disk_read_bytes_per_second','sum by(machine)(irate(node_disk_read_bytes_total{device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])) or sum by(machine)(irate(windows_physical_disk_read_bytes_total[5m]))')
record('disk_write_bytes_per_second','sum by(machine)(irate(node_disk_written_bytes_total{device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])) or sum by(machine)(irate(windows_physical_disk_write_bytes_total[5m]))')
record('network_receive_bytes_per_second','sum by(machine)(irate(node_network_receive_bytes_total{device=~"eth[0-9]+|enp.*|ens.*|eno.*"}[5m])) or sum by(machine)(irate(windows_net_bytes_received_total[5m]))')
record('network_transmit_bytes_per_second','sum by(machine)(irate(node_network_transmit_bytes_total{device=~"eth[0-9]+|enp.*|ens.*|eno.*"}[5m])) or sum by(machine)(irate(windows_net_bytes_sent_total[5m]))')
(OUT/'rules.yml').write_text(json.dumps({'groups':[{'name':'task-manager-normalized','rules':rules}]},indent=2),encoding='utf-8')

def target(expr,legend='',instant=False):return {'expr':expr,'legendFormat':legend,'refId':'A','datasource':DS,'instant':instant,'range':not instant}
def panel(title,expr,x,y,w=6,h=5,typ='stat',unit='short',color='#5794F2',legend='',desc='',link=None):
    exprs=expr if isinstance(expr,list) else [(expr,legend)]
    targets=[]
    for i,(e,l) in enumerate(exprs):
        t=target(e,l,typ in ['stat','table','bargauge']);t['refId']=chr(65+i);targets.append(t)
    p={'title':title,'type':typ,'gridPos':{'x':x,'y':y,'w':w,'h':h},'datasource':DS,'targets':targets,'description':desc,'fieldConfig':{'defaults':{'unit':unit,'color':{'mode':'fixed','fixedColor':color},'decimals':1,'noValue':'—','mappings':[],'thresholds':{'mode':'absolute','steps':[{'color':'green','value':None}]}},'overrides':[]}}
    if unit=='percent':p['fieldConfig']['defaults'].update({'min':0,'max':100})
    if title in ['工作频率','CPU 工作频率']:p['fieldConfig']['defaults']['decimals']=3
    if title=='逻辑 CPU 数量':p['fieldConfig']['defaults']['decimals']=0
    if link:p['fieldConfig']['defaults']['links']=[{'title':'查看详细信息','url':link,'targetBlank':False}]
    if typ=='stat':p['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'orientation':'auto','textMode':'auto','colorMode':'value','graphMode':'none','justifyMode':'auto','text':{'titleSize':12,'valueSize':24}}
    elif typ=='timeseries':
        p['fieldConfig']['defaults']['custom']={'drawStyle':'line','lineInterpolation':'smooth','lineWidth':1,'fillOpacity':12,'showPoints':'never','spanNulls':False,'axisLabel':'','axisPlacement':'auto'}
        p['options']={'tooltip':{'mode':'multi','sort':'desc'},'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull']}}
    elif typ=='bargauge':p['options']={'orientation':'horizontal','displayMode':'gradient','showUnfilled':True,'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False}}
    return p
def text(title,content,y,h=3):return {'type':'text','title':title,'gridPos':{'x':0,'y':y,'w':24,'h':h},'options':{'mode':'markdown','content':content}}
def row(title,y):return {'type':'row','title':title,'collapsed':False,'gridPos':{'x':0,'y':y,'w':24,'h':1},'panels':[]}
machine={'name':'machine','label':'机器','type':'custom','query':'PVE 宿主机 : pve,Ubuntu : ubuntu,Windows : windows,飞牛 : fnos','current':{'text':'PVE 宿主机','value':'pve'},'options':[{'text':n,'value':v,'selected':v=='pve'} for n,v in [('PVE 宿主机','pve'),('Ubuntu','ubuntu'),('Windows','windows'),('飞牛','fnos')]],'hide':0}
def dash(uid,title,panels,variables=None):
    for i,p in enumerate(panels):p['id']=i+1
    d={'uid':uid,'title':title,'schemaVersion':40,'version':1,'editable':True,'style':'dark','timezone':'Asia/Shanghai','refresh':'1s','timepicker':{'refresh_intervals':['1s','5s','10s','30s','1m']},'time':{'from':'now-15m','to':'now'},'tags':['PVE','任务管理器'],'graphTooltip':1,'panels':panels,'templating':{'list':variables or []},'links':[{'title':'总览','type':'link','url':'/d/pve-home','icon':'dashboard'},{'title':'CPU','type':'link','url':'/d/pve-cpu?var-machine=${machine}'},{'title':'内存','type':'link','url':'/d/pve-memory?var-machine=${machine}'},{'title':'磁盘','type':'link','url':'/d/pve-disk?var-machine=${machine}'},{'title':'网络','type':'link','url':'/d/pve-network?var-machine=${machine}'},{'title':'GPU','type':'link','url':'/d/pve-gpu'},{'title':'传感器','type':'link','url':'/d/pve-sensors'}]}
    if not variables:
        for link in d['links']:link['url']=link['url'].replace('${machine}','ubuntu' if uid=='pve-gpu' else 'pve')
    (OUT/('home.json' if uid=='pve-home' else uid+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

cpu_fresh=' and on(machine) (time() - lab_collector_last_success_seconds{collector="cpu"} < 150)'
gpu_fresh=' and on(machine) (time() - lab_collector_last_success_seconds{collector="gpu"} < 150)'
hw_fresh=' and on(machine) (time() - lab_collector_last_success_seconds{collector="bmc"} < 180)'
smart_fresh=' and on(machine) (time() - lab_collector_last_success_seconds{collector="smart"} < 900)'
ps=[text('PVE · 性能中心','**EPYC 7R13 · 48 核 / 96 线程 · 双 RTX 2080 Ti**  \n点击指标卡片进入详情。打开页面时系统指标每 1 秒采集，CPU / 磁盘 / 网络速率按相邻采样计算；硬件传感器 60 秒，磁盘健康 5 分钟。虚拟机内存显示客体系统内部用量。',0,3)]
items=[('CPU 利用率','lab:cpu_usage_percent{machine="pve"}','percent','#5794F2','cpu'),('CPU 工作频率','lab_cpu_busy_frequency_hertz{machine="pve",cpu=""}'+cpu_fresh,'hertz','#5794F2','cpu'),('内存 · 实际占用','lab:memory_used_bytes{machine="pve"}','bytes','#B877D9','memory'),('CPU 封装功耗','lab_cpu_package_power_watts'+cpu_fresh,'watt','#FFB357','cpu')]
for i,(title,e,u,c,link) in enumerate(items):ps.append(panel(title,e,i*6,3,unit=u,color=c,link='/d/pve-'+link+'?var-machine=pve'))
items=[('磁盘 · 读 / 写',[('lab:disk_read_bytes_per_second{machine="pve"}','读取'),('lab:disk_write_bytes_per_second{machine="pve"}','写入')],'Bps','#73BF69','disk'),('网络 · 接收 / 发送',[('lab:network_receive_bytes_per_second{machine="pve"}','接收'),('lab:network_transmit_bytes_per_second{machine="pve"}','发送')],'Bps','#FF9830','network'),('GPU 0 · 利用率','lab_gpu_utilization_percent{gpu="0"}'+gpu_fresh,'percent','#56D4C0','gpu'),('GPU 1 · 利用率','lab_gpu_utilization_percent{gpu="1"}'+gpu_fresh,'percent','#56D4C0','gpu')]
for i,(title,e,u,c,link) in enumerate(items):ps.append(panel(title,e,i*6,8,unit=u,color=c,link='/d/pve-'+link+'?var-machine=pve'))
ps.append(row('虚拟机 · 内部资源使用',13))
for idx,(m,n) in enumerate([('ubuntu','Ubuntu · 48 vCPU / 160 GiB'),('windows','Windows · 16 vCPU / 32 GiB'),('fnos','飞牛 · 16 vCPU / 32 GiB')]):
    y=14+idx*7;ps.append(row(n,y))
    for i,(title,key,u,c,link) in enumerate([('CPU','cpu_usage_percent','percent','#5794F2','cpu'),('内存使用','memory_used_bytes','bytes','#B877D9','memory'),('磁盘读取','disk_read_bytes_per_second','Bps','#73BF69','disk'),('网络接收','network_receive_bytes_per_second','Bps','#FF9830','network')]):ps.append(panel(title,f'lab:{key}{{machine="{m}"}}',i*6,y+1,unit=u,color=c,link='/d/pve-'+link+'?var-machine='+m))
ps.append(row('连接状态与数据来源',35))
p=panel('四台机器 · 采集连接','up{job=~"linux|windows"}',0,36,w=12,h=5,legend='{{machine}}')
p['fieldConfig']['defaults']['mappings']=[{'type':'value','options':{'0':{'text':'离线','color':'red'},'1':{'text':'在线','color':'green'}}}];ps.append(p)
ps.append(panel('硬件数据距上次成功采集','time() - lab_collector_last_success_seconds',12,36,w=12,h=5,unit='s',legend='{{machine}} / {{collector}}'))
ps.append(text('读数说明','- PVE 内存包含虚拟机在宿主机的实际占用；VM 内存按客体系统的「总量 − 可用量」显示。两者不能直接相加或互相替代。\n- GPU 属于 Ubuntu 直通硬件，总览展示的是同两张卡，不重复计数。\n- CPU 功耗是封装功耗；CPU＋GPU 合计不是整机功耗。当前无可信整机功耗数据。\n- VM 的 vCPU 可以在不同物理核之间调度，所以物理频率和温度仅在 PVE 页面显示。',41,5))
dash('pve-home','PVE · 任务管理器',ps,[machine])

ps=[text('CPU · ${machine}','PVE 显示真实物理硬件频率；虚拟机显示 vCPU 利用率，物理频率与功耗为「—」。PVE 的 CPU 0 / 48、1 / 49 等为同一物理核的 SMT 线程。频率表示忙碌期间平均频率，不是标称频率。最近 30 分钟使用临时实时缓存，更长时间范围使用每分钟历史。',0,3),panel('总利用率','lab:cpu_usage_percent{machine="$machine"}',0,3,unit='percent'),panel('逻辑 CPU 数量','lab:cpu_count{machine="$machine"}',6,3,unit='short'),panel('工作频率','lab_cpu_busy_frequency_hertz{machine="$machine",cpu=""}'+cpu_fresh,12,3,unit='hertz'),panel('CPU 封装功耗','lab_cpu_package_power_watts{machine="$machine"}'+cpu_fresh,18,3,unit='watt',color='#FFB357'),panel('CPU 利用率走势','lab:cpu_usage_percent{machine="$machine"}',0,8,w=12,h=7,typ='timeseries',unit='percent'),panel('各逻辑 CPU 利用率','lab:cpu_core_usage_percent{machine="$machine"}',12,8,w=12,h=7,typ='bargauge',unit='percent',legend='CPU {{cpu}}')]
ps.append(row('每个逻辑 CPU · 利用率与物理工作频率',15))
p=panel('CPU ${cpu}',[('lab:cpu_core_usage_percent{machine="$machine",cpu="$cpu"}','利用率'),('lab_cpu_busy_frequency_hertz{machine="$machine",cpu="$cpu"}'+cpu_fresh,'工作频率')],0,16,w=4,h=6,typ='timeseries',unit='percent')
p.update({'repeat':'cpu','repeatDirection':'h','maxPerRow':6});p['fieldConfig']['overrides']=[{'matcher':{'id':'byName','options':'工作频率'},'properties':[{'id':'unit','value':'hertz'},{'id':'min','value':0},{'id':'max','value':4000000000},{'id':'custom.axisPlacement','value':'right'},{'id':'color','value':{'mode':'fixed','fixedColor':'#FFB357'}}]}];p['options']['legend']={'showLegend':False};ps.append(p)
cpuvar={'name':'cpu','label':'逻辑 CPU','type':'query','datasource':DS,'query':{'query':'label_values(lab:cpu_core_usage_percent{machine="$machine"}, cpu)','refId':'cpu-var'},'definition':'label_values(lab:cpu_core_usage_percent{machine="$machine"}, cpu)','refresh':1,'sort':3,'multi':True,'includeAll':True,'current':{'text':['All'],'value':['$__all']},'options':[]}
dash('pve-cpu','CPU · 逐核性能',ps,[machine,cpuvar])

ps=[text('内存 · ${machine}','主读数采用系统内部「总量 − 可用量」。Linux 缓存与共享内存字段可能重叠，不能相加。下方同时保留 PVE 配置容量和宿主机占用，便于区分不同口径。',0,3)]
for i,(title,key) in enumerate([('已使用','memory_used_bytes'),('可用','memory_available_bytes'),('系统可见总量','memory_total_bytes'),('使用率','memory_used_percent')]):ps.append(panel(title,'lab:'+key+'{machine="$machine"}',i*6,3,unit='percent' if i==3 else 'bytes',color='#B877D9'))
ps.append(panel('已用 / 可用',[('lab:memory_used_bytes{machine="$machine"}','已用'),('lab:memory_available_bytes{machine="$machine"}','可用')],0,8,w=16,h=8,typ='timeseries',unit='bytes',color='#B877D9'))
ps.append(panel('PVE 配置容量','lab_vm_configured_memory_bytes{guest="$machine"} and on(machine) (time() - lab_collector_last_success_seconds{collector="inventory"} < 150)',16,8,w=8,h=4,unit='bytes',desc='仅虚拟机适用。'))
ps.append(panel('PVE 宿主机侧占用','lab_vm_host_memory_bytes{guest="$machine"} and on(machine) (time() - lab_collector_last_success_seconds{collector="inventory"} < 150)',16,12,w=8,h=4,unit='bytes',desc='QEMU 在宿主机侧的占用，与客体内部用量不同。'))
ps.append(panel('缓存 / 共享内存 / Swap',[('node_memory_Cached_bytes{machine="$machine"} or windows_memory_cache_bytes{machine="$machine"}','缓存'),('node_memory_Shmem_bytes{machine="$machine"}','共享内存'),('node_memory_SwapTotal_bytes{machine="$machine"} - node_memory_SwapFree_bytes{machine="$machine"}','Swap 已用'),('windows_memory_committed_bytes{machine="$machine"}','Windows 已提交')],0,16,w=24,h=8,typ='timeseries',unit='bytes',color='#B877D9'))
dash('pve-memory','内存 · 真实使用与容量',ps,[machine])

diskvar={'name':'disk','label':'设备','type':'query','datasource':DS,'query':{'query':'label_values(node_disk_info{machine="$machine"}, device)','refId':'disk-var'},'refresh':1,'multi':True,'includeAll':True,'current':{'text':['All'],'value':['$__all']},'hide':2}
ps=[text('磁盘 · ${machine}','Linux 总吞吐仅汇总整盘 sd / nvme 设备，避免将分区、LVM、RAID 重复累加。飞牛的直通机械盘和 NVMe 从飞牛内部采集。SMART 每 5 分钟读取，不主动唤醒休眠机械盘。',0,3)]
ps.append(panel('读取','lab:disk_read_bytes_per_second{machine="$machine"}',0,3,w=12,unit='Bps',color='#73BF69'));ps.append(panel('写入','lab:disk_write_bytes_per_second{machine="$machine"}',12,3,w=12,unit='Bps',color='#73BF69'))
ps.append(panel('每盘读取',[('irate(node_disk_read_bytes_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])','{{device}}'),('irate(windows_physical_disk_read_bytes_total{machine="$machine"}[5m])','{{disk}}')],0,8,w=12,h=8,typ='timeseries',unit='Bps',color='#73BF69'))
ps.append(panel('每盘写入',[('irate(node_disk_written_bytes_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])','{{device}}'),('irate(windows_physical_disk_write_bytes_total{machine="$machine"}[5m])','{{disk}}')],12,8,w=12,h=8,typ='timeseries',unit='Bps',color='#73BF69'))
ps.append(panel('读写 IOPS',[('irate(node_disk_reads_completed_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])','{{device}} 读'),('irate(node_disk_writes_completed_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m])','{{device}} 写'),('irate(windows_physical_disk_reads_total{machine="$machine"}[5m])','{{disk}} 读'),('irate(windows_physical_disk_writes_total{machine="$machine"}[5m])','{{disk}} 写')],0,16,w=12,h=8,typ='timeseries',unit='iops',color='#73BF69'))
ps.append(panel('平均读取延迟',[('irate(node_disk_read_time_seconds_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m]) / clamp_min(irate(node_disk_reads_completed_total{machine="$machine",device=~"sd[a-z]+|nvme[0-9]+n[0-9]+"}[5m]),0.001)','{{device}}'),('irate(windows_physical_disk_read_latency_seconds_total{machine="$machine"}[5m]) / clamp_min(irate(windows_physical_disk_reads_total{machine="$machine"}[5m]),0.001)','{{disk}}')],12,16,w=12,h=8,typ='timeseries',unit='s',color='#73BF69'))
ps.append(panel('文件系统使用率',[('100 * (1 - node_filesystem_avail_bytes{machine="$machine",fstype!~"tmpfs|devtmpfs|squashfs|overlay"}/node_filesystem_size_bytes{machine="$machine",fstype!~"tmpfs|devtmpfs|squashfs|overlay"})','{{mountpoint}}'),('100 * (1 - windows_logical_disk_free_bytes{machine="$machine",volume=~"[A-Z]:"}/windows_logical_disk_size_bytes{machine="$machine",volume=~"[A-Z]:"})','{{volume}}')],0,24,w=12,h=8,typ='bargauge',unit='percent',color='#73BF69'))
ps.append(panel('各磁盘温度','lab_disk_temperature_celsius{machine="$machine"}'+smart_fresh,12,24,w=12,h=8,typ='timeseries',unit='celsius',legend='{{disk}} · {{model}}',color='#FFB357'))
p=panel('SMART 健康','lab_disk_smart_passed{machine="$machine"}'+smart_fresh,0,32,w=12,h=6,legend='{{disk}} · {{model}}');p['fieldConfig']['defaults']['mappings']=[{'type':'value','options':{'1':{'text':'通过','color':'green'},'0':{'text':'异常','color':'red'}}}];ps.append(p)
ps.append(panel('通电时长','lab_disk_power_on_hours{machine="$machine"}'+smart_fresh,12,32,w=12,h=6,unit='h',legend='{{disk}}'))
ps.append(panel('关键 SMART 计数','lab_disk_smart_attribute_raw{machine="$machine"}'+smart_fresh,0,38,w=24,h=7,typ='table',legend='{{disk}} {{attribute}}'))
dash('pve-disk','磁盘 · 吞吐与健康',ps,[machine])

ps=[text('网络 · ${machine}','总览仅汇总 Linux 物理 / 客体主网卡，不把网桥与 tap 流量再次相加。虚拟网卡的标称 10 Gbps 不代表物理线路速度；PVE 物理端口的链路速率才代表连接能力。',0,3),panel('总接收','lab:network_receive_bytes_per_second{machine="$machine"}',0,3,w=12,unit='Bps',color='#FF9830'),panel('总发送','lab:network_transmit_bytes_per_second{machine="$machine"}',12,3,w=12,unit='Bps',color='#FF9830')]
for i,(title,direction) in enumerate([('每个接口接收','receive'),('每个接口发送','transmit')]):
    win='received' if direction=='receive' else 'sent'
    ps.append(panel(title,[(f'irate(node_network_{direction}_bytes_total{{machine="$machine",device!="lo"}}[5m])','{{device}}'),(f'irate(windows_net_bytes_{win}_total{{machine="$machine"}}[5m])','{{nic}}')],i*12,8,w=12,h=9,typ='timeseries',unit='Bps',color='#FF9830'))
ps.append(panel('链路速率',[('node_network_speed_bytes{machine="$machine",device=~"eth.*|enp.*|ens.*|eno.*"} > 0','{{device}}'),('windows_net_current_bandwidth_bytes{machine="$machine"}','{{nic}}')],0,17,w=12,h=7,unit='Bps',color='#FF9830'))
ps.append(panel('接收错误 / 丢包',[('irate(node_network_receive_errs_total{machine="$machine"}[5m])','{{device}} 错误'),('irate(node_network_receive_drop_total{machine="$machine"}[5m])','{{device}} 丢包'),('irate(windows_net_packets_received_errors_total{machine="$machine"}[5m])','{{nic}} 错误'),('irate(windows_net_packets_received_discarded_total{machine="$machine"}[5m])','{{nic}} 丢包')],12,17,w=12,h=7,typ='timeseries',unit='pps',color='#FF9830'))
dash('pve-network','网络 · 接口流量',ps,[machine])

ps=[text('GPU · Ubuntu 直通显卡','两张 RTX 2080 Ti 的指标由 Ubuntu 驱动直接读取。显存占用高不等于 GPU 正在运算；功率限制与实际功耗分别显示。GPU 温度、频率、功耗为驱动报告值。',0,3)]
for idx in range(2):
    y=3+idx*18;ps.append(row(f'GPU {idx} · RTX 2080 Ti · 22 GiB',y))
    for j,(title,key,unit,color) in enumerate([('GPU 利用率','utilization_percent','percent','#56D4C0'),('显存已用','memory_used_bytes','bytes','#B877D9'),('温度','temperature_celsius','celsius','#FFB357'),('功耗','power_watts','watt','#FF9830')]):ps.append(panel(title,f'lab_gpu_{key}{{gpu="{idx}"}}'+gpu_fresh,j*6,y+1,unit=unit,color=color))
    ps.append(panel('利用率与显存控制器忙碌度',[(f'lab_gpu_utilization_percent{{gpu="{idx}"}}'+gpu_fresh,'GPU'),(f'lab_gpu_memory_utilization_percent{{gpu="{idx}"}}'+gpu_fresh,'显存控制器')],0,y+6,w=12,h=7,typ='timeseries',unit='percent',color='#56D4C0'))
    ps.append(panel('功耗与温度',[(f'lab_gpu_power_watts{{gpu="{idx}"}}'+gpu_fresh,'功耗'),(f'lab_gpu_temperature_celsius{{gpu="{idx}"}}'+gpu_fresh,'温度')],12,y+6,w=12,h=7,typ='timeseries',unit='watt',color='#FF9830'))
    ps[-1]['fieldConfig']['overrides']=[{'matcher':{'id':'byName','options':'温度'},'properties':[{'id':'unit','value':'celsius'},{'id':'custom.axisPlacement','value':'right'}]}]
    for j,(title,key,unit) in enumerate([('核心频率','clock_hertz','hertz'),('显存频率','memory_clock_hertz','hertz'),('风扇','fan_percent','percent'),('功率限制','power_limit_watts','watt')]):ps.append(panel(title,f'lab_gpu_{key}{{gpu="{idx}"}}'+gpu_fresh,j*6,y+13,h=4,unit=unit,color='#56D4C0'))
ps.append(panel('CPU＋双 GPU 功耗合计 · 非整机','sum(lab_cpu_package_power_watts'+cpu_fresh+') + sum(lab_gpu_power_watts'+gpu_fresh+')',0,39,w=24,h=7,typ='timeseries',unit='watt',color='#FFB357'))
dash('pve-gpu','GPU · 双卡性能与功耗',ps)

ps=[text('硬件传感器 · PVE','CPU / CCD、内存、主板供电区域、风扇等读数来自宿主机内核或 BMC。不存在或无效的传感器显示为空；当前 BMC 整机功耗返回无效 0 W，已排除。',0,3),panel('CPU / CCD 温度','node_hwmon_temp_celsius{machine="pve"} * on(machine,chip,instance,job) group_left(chip_name) node_hwmon_chip_names{machine="pve",chip_name="k10temp"}',0,3,w=12,h=9,typ='timeseries',unit='celsius',legend='{{chip}} {{sensor}}',color='#FFB357'),panel('主板与 DIMM 温度','lab_bmc_temperature_celsius'+hw_fresh,12,3,w=12,h=9,typ='timeseries',unit='celsius',legend='{{sensor}}',color='#FFB357'),panel('CPU / 机箱风扇','lab_bmc_fan_rpm'+hw_fresh,0,12,w=12,h=9,typ='timeseries',unit='rpm',legend='{{sensor}}',color='#56D4C0'),panel('主板电压','lab_bmc_voltage_volts'+hw_fresh,12,12,w=12,h=9,typ='timeseries',unit='volt',legend='{{sensor}}'),panel('各采集模块状态','lab_collector_success',0,21,w=12,h=6,legend='{{machine}} {{collector}}'),panel('硬件数据年龄','time() - lab_collector_last_success_seconds',12,21,w=12,h=6,unit='s',legend='{{machine}} {{collector}}')]
dash('pve-sensors','传感器 · 温度与风扇',ps)
print('Generated',len(list(OUT.glob('*.json'))),'dashboards and',len(rules),'recording rules')

