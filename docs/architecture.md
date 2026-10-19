# 技术原理

## 为什么分两个存储通道

页面每秒刷新并不自动意味着 exporter 每秒采集，也不意味着显示的速率是实时值。项目把采集频率、查询范围和持久化频率分别控制。

历史 Prometheus 固定 60 秒采集与计算聚合规则，写入 `/var/lib/prometheus`，保留目标一天。实时 Prometheus 使用 `/run/prometheus-live`，活跃时 1 秒采集，空闲时 60 秒，保留目标一小时。Grafana 经自适应路由访问相应通道。这样打开页面不会把所有秒级采样持续写入历史磁盘。

`/run` 需确认为 tmpfs。它是非持久文件系统，不等于永远不写物理磁盘：系统压力下可能使用 swap。实时服务重启后旧数据消失。

## 活动检测

`src/adaptive_monitor.py` 使用 Python 标准库的 `ThreadingHTTPServer`。本机收到 `/api/v1/query` 或 `/api/v1/query_range` 请求时更新 `time.monotonic()` 活动时间。控制线程每秒检查一次：

1. 最近 60 秒有查询：将 live.yml 的采集/规则周期设为 1 秒、超时设为 900 ms。
2. 60 秒无查询：改回 60 秒采集/计算、10 秒超时。
3. 配置先写临时文件，通过 `promtool check config` 后原子替换，再发送 HUP。
4. 切换前检查实时 Prometheus `/-/ready`，避免启动阶段过早发送 HUP。
5. `/mode` 返回已应用的模式、周期、切换时间与错误；读取该接口不会触发实时模式。

判断依据是查询流量，不是浏览器窗口是否可见。后台标签页、其他客户端、主动调用路由的验收程序也可能保持活跃。仅关闭一个窗口不代表全部查询停止。

## 查询路由

查询起始时间或结束时间距当前超过 1860 秒时，整条查询送到历史通道；否则送到实时通道。1860 秒是约 30 分钟窗口加 60 秒容差。不会在一张图里自动拼接两个通道，也不会对丢失的秒级数据进行回填。

所有 `/api/v1/` 路由只接受本机请求。远程硬件采集器仅通过带 Bearer 令牌的 `/mode` 读取模式。Prometheus 两个实例仅监听 loopback。Grafana 数据源地址为 `http://127.0.0.1:9091`。

## 硬件采集

`src/lab_collector.py` 按角色运行线程：PVE 采集 turbostat、VM inventory、BMC、SMART；Ubuntu 采集 NVIDIA GPU；fnOS 采集 SMART。Windows 通过 windows_exporter 提供系统指标。

硬件采集器每 3 秒读取模式，模式读取失败或超过 10 秒未成功更新时按低频处理。任务完成后将指标写入临时文件，再原子替换 `.prom`，由 node_exporter textfile collector 提供给两个 Prometheus。

| 任务 | 活跃 | 空闲 |
|---|---:|---:|
| CPU/GPU | 1 秒 | 60 秒 |
| PVE VM inventory | 15 秒 | 60 秒 |
| BMC | 60 秒 | 60 秒 |
| SMART | 300 秒 | 300 秒 |

周期是任务开始间隔的目标。命令耗时、调度和网络会造成偏差；SMART/BMC 不会因页面打开而每秒读取。

## 缺失与新鲜度

每个任务输出 `lab_collector_success` 和 `lab_collector_last_success_seconds`。失败时该任务的数据文件被替换成状态指标，面板还限制最大数据年龄：CPU/GPU/VM 150 秒、BMC 180 秒、SMART 900 秒。系统聚合规则使用 `up == 1` 过滤离线目标。

指标显示为“—”可能是设备不支持、采集失败、目标离线或数据太旧；不能统一解释为数值为零。

## 仪表盘生成

生成链为 `build_dashboards.py → build_compact.py → build_dense.py`，保留了基础版、紧凑版和最终高密度版的构造步骤。统一入口是 `scripts/build_dashboards.py`，将最终七个仪表盘与规则复制到 `dashboards/`。

CPU 总利用率面板同时请求全部核心利用率和频率，再以本面板 transformation 只显示总量。重复核心面板通过 Dashboard 数据源读取变换前的结果，在本地按核心筛选，避免 96 个核心分别发出同样结构的后端请求。详见 [Grafana 查询共享文档](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/query-transform-data/share-query/)。

页面默认最近 15 分钟、1 秒刷新；历史时间范围可手动修改。小图为了有限像素采用有限绘图采样点，不能把页面曲线当作完整的每秒峰值存档。

