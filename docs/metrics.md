# 指标定义与解读

## CPU

Linux 使用 `node_cpu_seconds_total{mode="idle"}`，Windows 使用 `windows_cpu_time_total{mode="idle"}`。单核利用率为 `100 × (1 - irate(idle[5m]))`；整体利用率先对核取平均。结果限制在 0–100%，减少短采样间隔下计数器时间量化造成的轻微越界。

`irate` 使用窗口内最后两个有效计数样本，因此 5 分钟是搜索窗口，不是 5 分钟平均值。高频模式下约代表一秒间隔，低频模式下约代表一分钟间隔。这里 idle 之外的状态被算入非 idle；Linux iowait 的解释应结合系统负载，不等同于全部时间都在执行计算。

Windows 的 `core` 标签经 `label_replace` 统一为 `cpu`，用于相同的逐核面板。逻辑 CPU 数量不是物理核心数。

## CPU 频率与功耗

PVE 上 `turbostat` 采样 0.5 秒，用 `Bzy_MHz` 转换为 Hz。它表示忙碌期间平均工作频率，与 `/proc/cpuinfo` 的静态标称值、空闲时平均频率有不同含义。仪表盘不拿标称频率冒充动态频率。

CPU `PkgWatt` 是封装功耗，不能代表墙上插座的整机功耗；驱动、内核、处理器型号决定能否读取。当前实现要求 turbostat 输出预期列，主要基于实际验证过的单路平台，多路封装求和与其他架构需要适配。

客体 vCPU 会在物理逻辑核之间调度，虚拟机通常无法获得可信的物理核频率和封装功耗。本模板在客体中允许这些指标缺失，不用虚构的固定频率填充。

## 内存

| 指标 | 公式/来源 |
|---|---|
| Linux 实际已用 | `MemTotal - MemAvailable` |
| Windows 实际已用 | `physical_total_bytes - available_bytes` |
| 内部使用率 | 实际已用 / 系统可见总量 |
| 配置容量 | PVE VM inventory 的 `maxmem` |
| 宿主机侧 VM 占用 | PVE VM inventory 的 `memhost`（提供时） |

Linux 的 MemAvailable 考虑可回收缓存，所以这里不是简单地把所有缓存都算作无法释放的已用。PVE 宿主机看到的 VM 占用与客体内部应用/缓存口径不同，不应相加或强行要求相等。PVE 宿主机页面的 VM 配置容量不适用，显示缺失是正常行为。

## 磁盘

吞吐率由累计字节计数的 `irate` 计算，IOPS 来自读写完成次数，平均读取延迟来自累计读取时间 / 读取次数。零 I/O 时分母使用最小值保护。Linux 总量筛选整盘 `sd[a-z]+` 和 `nvme[0-9]+n[0-9]+`，避免把分区和 LVM 多层计数重复加总。

因此 virtio 的 `vd*`、软件 RAID `md*`、multipath、其他设备命名需要按拓扑调整筛选，不能直接假定所有磁盘已覆盖。由飞牛直接管理的直通盘，其物理 SMART 从飞牛采集，不会假装仍由 PVE 管理。

SMART 使用 `smartctl -n standby -a -j`，跳过 QEMU 模型虚拟盘，读取温度、健康状态、通电时间及常用故障计数。休眠盘或不支持的字段可缺失；应在自己的控制器上确认待机检查行为。部分采集字段不会保留进 Prometheus 白名单，只有当前图表需要的数据持久化。

## 网络

Linux 总量汇总 `eth* / enp* / ens* / eno*`，避免桥、tap 和 veth 对同一数据重复计数。逐接口图用于更细的分析。bond、无线网卡、自定义接口名需要调整规则。Windows 多适配器可能包含虚拟接口，也需按实际拓扑筛选。

总览磁盘和网络趋势使用读写/收发总吞吐，表格仍分别显示两个方向。单位为 B/s（字节/秒），链路位速率与字节吞吐不要混淆。

## GPU 与温度

NVIDIA GPU 位于直通 GPU 的 Ubuntu 客体，通过 `nvidia-smi --query-gpu` 读取利用率、显存、温度、功耗、功率上限、核心/显存频率与风扇。显存容量来自驱动而非显卡型号推断；高显存占用不代表高计算利用率。

GPU 功耗是驱动报告值；“功率上限”是限制值，与当前功耗分列。CPU+GPU 功耗不能称为整机功耗。本项目不把无效的 BMC 0 W 当作整机读数。

node_exporter 的 hwmon、IPMI BMC 和 SMART 分别覆盖 CPU/主板/磁盘等温度来源。CPU “最高温度”表达式与硬件传感器标签有关，迁移主板或 CPU 型号后应检查匹配条件。

## 规则与保留

聚合指标前缀 `lab:`，自定义硬件原始指标前缀 `lab_`。实际公式位于 `dashboards/rules.yml`，原始指标保留集合位于 `src/metric-allowlist.json`。导出的原始指标不一定全部写入数据库。新增图表后需要重新生成并更新两个 Prometheus 配置中的白名单。
