#!/bin/bash
set -euo pipefail
mode="$1"
stage="${2:-/var/tmp/lab-stage}"
test ! -e /usr/local/bin/node_exporter || /usr/local/bin/node_exporter --version
echo 'b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63  '"$stage/node_exporter.tar.gz" | sha256sum -c -
tar -xzf "$stage/node_exporter.tar.gz" -C "$stage"
install -m 0755 "$stage/node_exporter-1.12.1.linux-amd64/node_exporter" /usr/local/bin/node_exporter
id node_exporter >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin node_exporter
install -d -m 0755 /var/lib/node_exporter/textfile /etc/node_exporter
install -m 0644 "$stage/lab_collector.py" /usr/local/lib/lab_collector.py
cat >/etc/systemd/system/node_exporter.service <<'EOF'
[Unit]
Description=Personal monitoring system metrics
After=network-online.target
[Service]
User=node_exporter
Group=node_exporter
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100 --web.config.file=/etc/node_exporter/web.yml --collector.textfile.directory=/var/lib/node_exporter/textfile --collector.filesystem.mount-points-exclude=^/(dev|proc|sys|run|var/lib/docker/.+|var/lib/containers/.+|snap/.+)($|/) --collector.netdev.device-exclude=^(veth.*|fwbr.*|fwpr.*|fwln.*|lo)$
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/lab-hardware.service <<EOF
[Unit]
Description=Personal monitoring hardware telemetry ($mode)
After=network-online.target
[Service]
ExecStart=/usr/bin/python3 /usr/local/lib/lab_collector.py $mode
Restart=on-failure
RestartSec=10
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=full
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
chown node_exporter:node_exporter /etc/node_exporter/web.yml
chmod 0600 /etc/node_exporter/web.yml
systemctl daemon-reload
systemctl enable --now node_exporter lab-hardware
systemctl is-active node_exporter lab-hardware
