"""Deploy this merged checkout with reversible backups; no scene operations."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
USER=Path.home()
assert str(USER).lower() == r'C:\Users\sasch'.lower(), 'Run elevation as the same Windows user'
sys.stdout=open(ROOT/'.deployment-log.txt','a',encoding='utf-8',buffering=1)
sys.stderr=sys.stdout
STAMP=time.strftime('%Y%m%d-%H%M%S')
BACKUP=ROOT/'.deployment-backup'/STAMP
BACKUP.mkdir(parents=True)
manifest=[]
def backup(path):
    path=Path(path)
    if not path.exists():return
    dest=BACKUP/str(len(manifest))
    if path.is_dir():shutil.copytree(path,dest)
    else:shutil.copy2(path,dest)
    manifest.append({'original':str(path),'backup':str(dest)})
    (BACKUP/'manifest.json').write_text(json.dumps(manifest,indent=2))
# Parse configs before any deployment. Do not reset unreadable files.
claude_paths=[USER/'.claude.json',Path(os.environ['APPDATA'])/'Claude/claude_desktop_config.json']
packages=Path(os.environ['LOCALAPPDATA'])/'Packages'
claude_paths+=list(packages.glob('Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json'))
configs={p:json.loads(p.read_text(encoding='utf-8-sig')) for p in claude_paths if p.exists()}
for p in [USER/'.codex/config.toml',*configs.keys(),Path(os.environ['LOCALAPPDATA'])/'3dsmax-mcp',USER/'.claude/skills/3dsmax-mcp-dev',USER/'.agents/skills/3dsmax-mcp-dev']:
    backup(p)
package=Path(os.environ['ProgramData'])/'Autodesk/ApplicationPlugins/3dsmax-mcp'
backup(package)
legacy=[]
for year in range(2023,2028):
    maxdir=Path('C:/Program Files/Autodesk')/f'3ds Max {year}'
    for rel in ['plugins/mcp_bridge.gup','scripts/mcp/mcp_server.ms','scripts/startup/mcp_autostart.ms']:
        p=maxdir/rel
        if p.exists():backup(p);legacy.append(p)
# Deploy all staged files and validate byte-for-byte before disabling the legacy copies.
stage=ROOT/'.staged-bundle'
assert (stage/'PackageContents.xml').is_file()
package.mkdir(parents=True,exist_ok=True)
for src in stage.rglob('*'):
    if src.is_file():
        dst=package/src.relative_to(stage);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256(dst.read_bytes()).digest(),dst
for p in legacy:
    # Individual known files only; retain a sibling rollback copy outside loadable extensions.
    dst=p.with_name(p.name+'.pre-'+STAMP)
    p.rename(dst)
# Current native binaries are installed. Preserve all other user config values.
sys.path.insert(0,str(ROOT))
import install
install.deploy_config(tool_profile='full')
entry={'command':str(ROOT/'.venv/Scripts/3dsmax-mcp.exe'),'args':[],'env':{'MCP_TOOL_PROFILE':'full'}}
for p,cfg in configs.items():
    cfg.setdefault('mcpServers',{})['3dsmax-mcp']=dict(entry,**({'type':'stdio'} if p.name=='.claude.json' else {}))
    p.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
subprocess.run([sys.executable,str(ROOT/'scripts/build_skill.py'),'--target','both'],check=True)
print('DEPLOYED',package)
print('BACKUP',BACKUP)
print('CLAUDE_CONFIGS',len(configs))
