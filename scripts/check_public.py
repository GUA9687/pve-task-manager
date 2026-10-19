"""Conservative static preflight for accidental private material; no network access."""
import pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
patterns={
    'private IPv4':r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
    'user home path':r'(?i)[A-Z]:[\\/]Users[\\/][^\s]+',
    'private key':r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
    'GitHub credential':r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
}
issues=[];count=0
for p in ROOT.rglob('*'):
    if not p.is_file() or any(x in p.relative_to(ROOT).parts for x in ['.git','build','__pycache__']):continue
    if p.relative_to(ROOT).as_posix().startswith('src/dashboards/'):continue
    if p.suffix=='.png':continue
    if p.suffix in ['.db','.msi','.zip','.gz','.key','.pem','.log'] or p.name in ['.env','inventory.json']:
        issues.append((str(p.relative_to(ROOT)),'private/generated file'));continue
    count+=1
    try:txt=p.read_text(encoding='utf-8')
    except UnicodeError:issues.append((str(p.relative_to(ROOT)),'unexpected binary'));continue
    for name,pattern in patterns.items():
        if re.search(pattern,txt):issues.append((str(p.relative_to(ROOT)),name))
print('Scanned',count,'text files')
for p,kind in issues:print(kind+': '+p)
sys.exit(bool(issues))

