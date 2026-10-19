#!/bin/bash
set -euo pipefail
cd /var/tmp/lab-platform
echo '2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0  prometheus.tar.gz' | sha256sum -c -
echo 'c48765988fd88572607e4ea670251af8a8e64ab3e360d0f3cf67a6f3587b92ab  grafana.tar.gz' | sha256sum -c -
id prometheus >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin prometheus
id grafana >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin grafana
install -d /opt/grafana /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards /var/lib/grafana/dashboards /var/log/grafana /etc/prometheus /var/lib/prometheus
tar -xzf grafana.tar.gz --strip-components=1 -C /opt/grafana
tar -xzf prometheus.tar.gz
install -m 0755 prometheus-3.15.0.linux-amd64/prometheus prometheus-3.15.0.linux-amd64/promtool /usr/local/bin/
chown -R prometheus:prometheus /var/lib/prometheus /etc/prometheus
chown -R grafana:grafana /var/lib/grafana /var/log/grafana /etc/grafana
cat >/etc/systemd/system/prometheus.service <<'EOF'
[Unit]
Description=Personal monitoring time series database
After=network-online.target
[Service]
User=prometheus
ExecStart=/usr/local/bin/prometheus --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/var/lib/prometheus --storage.tsdb.retention.time=1d --storage.tsdb.retention.size=50MB --storage.tsdb.wal-segment-size=10MB --web.listen-address=127.0.0.1:9090
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=full
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/grafana.service <<'EOF'
[Unit]
Description=Personal PVE task manager dashboard
After=network-online.target prometheus.service
[Service]
User=grafana
WorkingDirectory=/opt/grafana
ExecStart=/opt/grafana/bin/grafana server --homepath=/opt/grafana --config=/etc/grafana/grafana.ini
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=full
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
echo 'Platform binaries ready'
