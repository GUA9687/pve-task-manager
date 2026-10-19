# 运行维护与验收

## 查看状态而不唤醒高频

在监控节点本地执行：

```sh
curl -s http://127.0.0.1:9091/mode
journalctl -u adaptive-monitor -n 20 --no-pager
systemctl is-active prometheus prometheus-live adaptive-monitor grafana
```

关掉所有查询页面后等待约 60 秒，再看 `active:false`、`interval:60`、`history_interval:60` 和空的 `error`。日志应有 `Live sampling: 60s`。重新打开面板会切到 1 秒。直接读模式不会延长活跃时间；向路由发送 PromQL 查询会延长。

如要验证真实间隔，可直接向 **9093** 查询 `timestamp(up{job=~"linux|windows"})` 的时间序列，比较连续不同时间戳的差值，避免只看配置文件。切换边界会有一个非整分钟的间隔；随后应稳定约 60 秒。查询 9090/9093 本身不经过活动检测。

## 基础验收

`scripts/validate_metrics.py` 在监控节点执行，默认直接查询历史 9090。它检查面板中的 PromQL 是否成功，并报告空结果。它不是把任何空结果都认定为错误：Windows/Linux 分支、宿主机上不适用的 VM 容量、客体不存在的物理传感器都会正常为空。检查实时通道时将脚本中的端口改为 9093。

关键项目：

- `up` 中四台目标在线，`count by(machine)(lab:cpu_core_usage_percent)` 与实际逻辑 CPU 数一致。
- 主机有动态频率、CPU 功耗；支持的 GPU 有温度和功耗。
- `lab_collector_success` 与最后成功时间合理；无效读数不当成 0。
- 磁盘/网络筛选与实际拓扑一致，客体内存没有误用配置容量。
- Grafana 页面能点进正确机器，CPU 共享结果显示每核曲线。
- 退出所有面板后的降频、重新访问后的升频均符合日志。

原部署验收包含 96/48/16/16 个逻辑 CPU、两张 NVIDIA GPU、PVE 与 fnOS 物理磁盘 SMART，最终 280 个参数化查询检查无查询错误。公开版本在此基础上参数化 VM 映射和部署地址，需在新环境重新验收，不能把原部署结果当作任意硬件保证。

## 存储预算

| 项目 | 设置 |
|---|---|
| 持久历史 | 60 秒采集，时间保留 1d，大小阈值 50MB |
| 历史 WAL | segment 10MB |
| 实时缓存 | `/run/prometheus-live`，保留目标 1h / 160MB |
| journald | 总预算 8M，单文件 2M |
| Grafana 日志 | warn |
| Go 堆内存目标 | Grafana 512MiB；每个 Prometheus 256MiB |

约千条保留指标、每分钟采样时，压缩样本本体约 1.5–3 MB/天是容量估算，索引、WAL、活动数据、文件系统和 journal 另计。原部署早期历史目录约 27 MiB，journal 约 7 MiB；并非完整一天稳态测量，也不是对未来增长的承诺。

`retention.size` 不是磁盘硬配额；活动 WAL、Head 和删除时机仍可能超过阈值，时间与大小限制也可能使实际可查询历史短于一天。实时通道保留时间同样不是秒级精确删除承诺。严格“总计不超过 100 MB”需要额外配额和容量保护，而当前实现没有这个保证。软件、备份、Grafana 数据库和截图不包含在上述时序数据预算中。

```sh
du -sh /var/lib/prometheus /run/prometheus-live
journalctl --disk-usage
```

`GOMEMLIMIT` 是 Go 运行时软目标，不是进程 RSS 硬限制。调整容器资源时不要把它误当 cgroup 限额。

## 备份与恢复

```sh
python3 /usr/local/sbin/backup-monitor-config.py
```

该脚本在 `/var/backups/pve-monitor/` 创建 root 专用 tar.gz，包含实际配置、服务文件、面板和通过 SQLite online backup 生成的 Grafana 数据库。**其中含凭据，只能私下保存，不能提交 GitHub。** 不包含历史 Prometheus 数据，也不包含所有客体采集端配置与软件二进制。

完整恢复建议使用平台 LXC 的正常备份，并另行保存各采集端配置。恢复单独配置时先停相应服务，核对版本和权限，恢复数据库与配置，运行 promtool 后启动。不要向运行中的 SQLite 数据库直接覆盖文件。

## 常见问题

| 现象 | 检查 |
|---|---|
| 关闭页面仍 1 秒 | 是否还有后台标签页、其他客户端或验收程序在查询 9091 |
| 面板暂时空白 | 启动/重启积累期、时间范围、目标 up、规则计算、新鲜度 |
| 高频模式 target down | 900ms scrape timeout 是否适合设备与网络；若延长需同时协调采样周期 |
| CPU 频率固定/缺失 | 是否在 VM 内看物理指标；turbostat 支持与权限、实际空闲/频率状态 |
| GPU 不可见 | Ubuntu 的 nvidia-smi、直通状态、驱动支持和 collector 日志 |
| SMART 缺失 | 待机、虚拟盘、控制器透传、权限、设备过滤条件 |
| 磁盘/网络总量不对 | 检查设备命名和多层拓扑，避免重复计数或筛选遗漏 |
| 改面板后恢复旧值 | provisioning 会重新载入文件；应修改源 JSON/生成器 |
| 地址变化后离线 | 更新 inventory、两通道 target、node 模式 URL、Windows 防火墙来源 |

切换配置通过 `systemctl kill -s HUP prometheus prometheus-live`；不是所有发行版 unit 都支持 `systemctl reload`。平台设置修改前先备份，并确认自适应控制器不会和手工写 live.yml 同时发生。

