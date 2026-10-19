"""Generate the tracked dashboards from the three incremental layout generators."""
import pathlib,runpy,shutil
root=pathlib.Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'src/build_dense.py'))
(root/'dashboards').mkdir(exist_ok=True)
for p in (root/'src/dashboards').iterdir():
    if p.suffix in ('.json','.yml'):shutil.copyfile(p,root/'dashboards'/p.name)
print('Published generated dashboards to dashboards/')

