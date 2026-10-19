import importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('render',ROOT/'scripts/render_config.py')
render=importlib.util.module_from_spec(spec);spec.loader.exec_module(render)

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.inv={'monitor_host':'monitor.test','machines':{k:k+'.test' for k in ['pve','ubuntu','windows','fnos']},'vm_map':{'201':'ubuntu','202':'windows','203':'fnos'}}
        # Synthetic formatting fixtures only, not deployable credentials.
        self.env={k:'test-fixture-not-a-real-secret' for k in ['EXPORTER_PASSWORD','ADAPTIVE_TOKEN','GRAFANA_ADMIN_PASSWORD']}
        self.env['EXPORTER_PASSWORD_HASH']='$2b$12$'+'.'*53
    def test_missing_secret_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d)/'new'
            with self.assertRaises(ValueError):render.render(self.inv,out,{})
            self.assertFalse(out.exists())
    def test_example_hosts_rejected(self):
        self.inv['monitor_host']='example.invalid'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):render.render(self.inv,pathlib.Path(d)/'new',self.env)
    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):render.render(self.inv,d,self.env)
    def test_generated_roles_ports_and_private_values(self):
        with tempfile.TemporaryDirectory() as d:
            out=render.render(self.inv,pathlib.Path(d)/'new',self.env)
            for name in ['prometheus.yml','live.yml']:
                c=json.loads((out/'platform/etc/prometheus'/name).read_text())
                self.assertEqual(c['global']['scrape_interval'],'60s')
                jobs={j['job_name']:j for j in c['scrape_configs']}
                self.assertEqual(jobs['linux']['basic_auth']['password'],self.env['EXPORTER_PASSWORD'])
                self.assertEqual(jobs['windows']['static_configs'][0]['targets'],['windows.test:9182'])
            node=json.loads((out/'pve/etc/node_exporter/adaptive.json').read_text())
            self.assertEqual(node['vm_map'],self.inv['vm_map'])
            self.assertEqual(node['url'],'http://monitor.test:9091/mode')
            self.assertEqual(len(list((out/'platform/var/lib/grafana/dashboards').glob('*.json'))),7)

if __name__=='__main__':unittest.main()
