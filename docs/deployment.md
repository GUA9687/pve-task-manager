# 部署指南

## 范围和前提

模板面向单节点 PVE、Ubuntu NVIDIA GPU 客体、Windows 客体及 fnOS 客体。监控平台可运行在独立 Debian 12 非特权 LXC，示例资源为 2 vCPU / 2 GiB RAM / 20 GB 磁盘。LXC ID、网桥和 IP 由部署者选择。本仓库不自动创建虚拟机，不配置公网入口，不修改 GPU 直通。

先确认四台机器可从监控节点访问：Linux exporter 9100、Windows exporter 9182；硬件采集器需要访问监控节点 9091。浏览器访问 Grafana 3000。网络应为可信管理网，限制采集端口的来源。IP 最好做 DHCP 保留或静态配置。

基线版本和校验值见 [第三方组件](third-party.md)。平台与 Linux 安装脚本期待预先下载到指定 staging 目录的安装包，并校验 SHA256；不会自行下载或升级操作系统。

## 1. 准备源码和私有配置

```sh
git clone https://github.com/GUA9687/pve-task-manager.git
cd pve-task-manager
python3 scripts/build_dashboards.py
cp config/inventory.example.json config/inventory.json
```

编辑 `config/inventory.json`，将 `.example.invalid` 替换成实际 IPv4 或 DNS 主机名，将 VM ID 改成自己的编号。机器角色字符串保留 `pve / ubuntu / windows / fnos`，仪表盘使用这些标签。当前渲染器不支持 IPv6 字面量。

渲染器从环境变量读取以下内容，不会生成或公开可用的默认密码：

| 环境变量 | 用途 |
|---|---|
| `EXPORTER_PASSWORD` | Linux exporter 的 monitor 用户密码 |
| `EXPORTER_PASSWORD_HASH` | 上述密码的 bcrypt 哈希 |
| `ADAPTIVE_TOKEN` | 模式查询 Bearer 令牌 |
| `GRAFANA_ADMIN_PASSWORD` | 新 Grafana 数据库的初始 admin 密码 |

三个原始秘密均至少 20 字符，无换行。可以用本地密码管理器生成随机值；bcrypt 可用 `htpasswd -nBC 12 monitor` 交互生成，提取用户名冒号后的哈希。不要把秘密写进终端命令历史、Git 或 issue。渲染器只检查格式，部署者必须保证 bcrypt 哈希与明文密码对应。

```sh
python3 scripts/render_config.py --inventory config/inventory.json --output build/deployment
```

输出 `build/deployment/platform/`、`pve/`、`ubuntu/`、`fnos/` 的文件树。该命令只生成文件，不安装、不联网、不重启服务；已存在的输出目录会被拒绝覆盖。`build/` 和私有 inventory 已被 Git 忽略。在 Windows 上生成时还应使用 NTFS ACL 限制目录访问；POSIX chmod 不能替代 Windows ACL。

## 2. 监控节点

在目标 Debian 节点以 root 准备 `/var/tmp/lab-platform/`，放入对应版本的 `prometheus.tar.gz` 和 `grafana.tar.gz`，然后运行 `scripts/install-platform.sh`。它创建 prometheus/grafana 系统用户并安装二进制与基础服务，尚不启动完整平台。

将渲染出的 `platform/` 文件树按同名绝对路径安装到目标节点，例如 `platform/etc/prometheus/live.yml` 对应 `/etc/prometheus/live.yml`。不要在已有服务上未经检查整树覆盖。渲染版本的 systemd 服务应在基础安装之后安装，包含实时通道、路由和内存配置。

权限要求：

```sh
chown -R prometheus:prometheus /var/lib/prometheus
chown root:prometheus /etc/prometheus/*.yml
chmod 640 /etc/prometheus/*.yml
chown -R grafana:grafana /var/lib/grafana /var/log/grafana /etc/grafana
chmod 600 /etc/grafana/admin-password
chmod 600 /etc/pve-monitor/adaptive.json
chmod 755 /usr/local/lib/adaptive_monitor.py
```

Grafana ini 通过 `$__file{...}` 读取初始密码。该设置仅用于初始化新数据库，不会替换已有用户的密码。不要复制原部署的 Grafana 数据库到公开项目。

检查 `/run` 是否 tmpfs：`findmnt /run`。如果不是，请先为实时数据配置合适的易失存储，否则不能声称秒级数据仅在内存中。

```sh
promtool check config /etc/prometheus/prometheus.yml
promtool check config /etc/prometheus/live.yml
promtool check rules /etc/prometheus/rules.yml
systemctl daemon-reload
systemctl restart systemd-journald
systemctl enable --now prometheus prometheus-live adaptive-monitor grafana
systemctl is-active prometheus prometheus-live adaptive-monitor grafana
```

这些命令需在监控节点运行，不是在 PVE 宿主机误执行。journald 限额适用于该监控节点的整个 journal，最好让监控服务位于独立容器。

## 3. PVE、Ubuntu、fnOS 的 Linux 采集器

在每台 Linux 机器准备 `/var/tmp/lab-stage/`，放入 `node_exporter.tar.gz` 和 `src/lab_collector.py`。复制对应角色的渲染配置到 `/etc/node_exporter/`，令牌文件 root:root 0600；web.yml 将由脚本改为 node_exporter 可读。

PVE 依赖 `python3`、`turbostat`（Debian 常见于 linux-cpupower）、`ipmitool`、`smartmontools`，以及系统自带的 `pvesh`；需确认设备接口和命令路径存在。Ubuntu 需要可正常工作的 NVIDIA 驱动与 `nvidia-smi`。fnOS 需要 `smartctl`；不要为了安装采集器替换其发行版内核或破坏系统管理服务。

```sh
# 在相应机器选择且只运行对应角色
bash scripts/install-node.sh pve /var/tmp/lab-stage
bash scripts/install-node.sh ubuntu /var/tmp/lab-stage
bash scripts/install-node.sh fnos /var/tmp/lab-stage
```

安装脚本启用 node_exporter 和 lab-hardware。硬件采集器以 root 运行以访问硬件接口，node_exporter 使用独立非登录用户；详见安全边界。不要把这三个命令全部运行在同一台机器。

PVE 角色使用 `adaptive.json` 中 `vm_map`，只枚举显式配置的三个 VM；OpenWrt 等其他 VM 不会自动加入。

## 4. Windows

在 Windows 下载已固定版本的 MSI，与 `scripts/install-windows-monitor.ps1` 放在同一目录，用管理员 PowerShell 执行：

```powershell
.\install-windows-monitor.ps1 -MonitorAddress <监控节点的实际IPv4地址>
```

参数需要实际 IP，不能保留尖括号。脚本检查管理员权限、校验安装包，安装 CPU/磁盘/内存/网络等 collectors，将采集端口设为 9182，并将安装器防火墙规则的来源限制为监控节点。之后仍应检查是否已有其他更宽的入站规则；安装规则不会自动收窄先前手工创建的规则。脚本不安装 Windows SSH。

```powershell
Get-Service windows_exporter
Invoke-WebRequest http://127.0.0.1:9182/health
```

日志保存在安装脚本目录，不应提交到公开仓库。

## 5. 打开与验收

访问 `http://<监控节点>:3000/d/pve-home?kiosk&refresh=1s`，用自行设置的 Grafana 账号登录。仪表盘通过 provisioning 加载，默认首页来自 home.json。

按 [运行维护](operations.md) 验证四个 up、每核指标数、GPU、硬件状态与关闭页面后的自动降频。第一次打开需要等待采集和两个计数样本，刚接入的图表没有旧历史，实时服务重启后也需重新积累。

## 修改与升级

修改源生成器后重新运行构建，将 `dashboards/*.json`、`rules.yml` 和刷新过的白名单一起部署。自适应服务和安装脚本的参数仍有固定约定，升级 Prometheus/exporter/Grafana 前应核对指标名、配置和 API。不要仅改图表就假设新增指标已持久化。

配置模板与生成器是可维护交付物；目前没有在全新主机上验证自动重装全过程。

