import pathlib,sqlite3,tarfile,os,datetime
root=pathlib.Path('/var/backups/pve-monitor');root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
db=root/('grafana-'+stamp+'.db')
src=sqlite3.connect('/var/lib/grafana/grafana.db');dst=sqlite3.connect(db);src.backup(dst);dst.close();src.close();os.chmod(db,0o600)
archive=root/('configuration-'+stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as t:
 for p in ['/etc/grafana','/etc/prometheus','/etc/systemd/system/grafana.service','/etc/systemd/system/prometheus.service','/var/lib/grafana/dashboards','/etc/pve-monitor','/usr/local/lib/adaptive_monitor.py','/etc/systemd/system/prometheus-live.service','/etc/systemd/system/adaptive-monitor.service','/etc/systemd/system/grafana.service.d','/etc/systemd/system/prometheus.service.d','/etc/systemd/system/prometheus-live.service.d','/etc/systemd/journald.conf.d/monitor-budget.conf']:
  t.add(p,arcname=p.lstrip('/'))
 t.add(db,arcname='var/lib/grafana/grafana.db')
os.chmod(archive,0o600);db.unlink();print(str(archive))
