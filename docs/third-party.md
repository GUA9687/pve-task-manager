# 第三方组件与版本基线

以下是原部署安装包基线，不表示自动追踪最新版本。安装辅助脚本校验确切文件的 SHA256；换包时应重新从官方来源核验校验值并验收指标兼容性。

| 组件 | 基线版本 | 上游 |
|---|---|---|
| Grafana | 13.2.4 | https://github.com/grafana/grafana |
| Prometheus | 3.15.0 | https://github.com/prometheus/prometheus |
| node_exporter | 1.12.1 | https://github.com/prometheus/node_exporter |
| windows_exporter | 0.31.9 | https://github.com/prometheus-community/windows_exporter |
| Python | 3.11+ | https://www.python.org/ |

```text
prometheus.tar.gz
2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0
grafana.tar.gz
c48765988fd88572607e4ea670251af8a8e64ab3e360d0f3cf67a6f3587b92ab
node_exporter.tar.gz
b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63
windows_exporter-0.31.9-amd64.msi
1e8a3898e8febaa475e008ffd2e729e1bef84ecbcb6875910546ee0798e96126
```

仓库没有打包这些组件的二进制或上游源码。Grafana、Prometheus、各 exporter、turbostat、ipmitool、smartmontools 和 NVIDIA 工具均保留各自的许可证、商标和使用条件；请以所下载版本的上游许可文件为准。公开本项目不会改变上游许可。

本仓库目前未单独选择项目许可证；公开可见本身不等于授予任意用途的许可。

## 设计参考

- [Prometheus 本地存储与保留](https://prometheus.io/docs/prometheus/latest/storage/)
- [Prometheus 配置与采集参数](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [PromQL irate](https://prometheus.io/docs/prometheus/latest/querying/functions/#irate)
- [node_exporter textfile collector](https://github.com/prometheus/node_exporter#textfile-collector)
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Grafana 查询共享](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/query-transform-data/share-query/)

