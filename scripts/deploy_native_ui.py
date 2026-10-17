"""Install the native-only UI and retire exact legacy slot macros with backups."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import time
import winreg

ROOT = Path(__file__).resolve().parents[1]


class DeploymentError(RuntimeError):
    """A precondition or verification step failed; nothing further is installed."""


def deploy(log):
    backup = ROOT/'.deployment-backup'/('native-ui-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    manifest = []

    def preserve(path):
        if path.exists():
            copy = backup/str(len(manifest))
            shutil.copy2(path, copy)
            manifest.append({'original': str(path), 'backup': str(copy)})
            (backup/'manifest.json').write_text(json.dumps(manifest, indent=2))

    package = Path(os.environ['ProgramData'])/'Autodesk/ApplicationPlugins/3dsmax-mcp'
    if not (package/'PackageContents.xml').exists():
        raise DeploymentError('Activate the native bundle before deploying this update')
    src = ROOT/'maxscript/mcp_server.ms'
    dst = package/'Contents/scripts/mcp_server.ms'
    preserve(dst)
    shutil.copy2(src, dst)
    if hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256(dst.read_bytes()).digest():
        raise DeploymentError(f'Copied bundle script does not match {src}; restore from {backup}')
    stage = ROOT/'.staged-bundle/Contents/scripts/mcp_server.ms'
    if stage.parent.exists():
        shutil.copy2(src, stage)

    retired = ['MCP Server-MCP_Slot1.mcr', 'MCP Server-MCP_Slot2.mcr', 'MCP Server-MCP_Slot3.mcr',
               'MCP Server-MCP_Manager.mcr', 'MCP-MCP_Start.mcr', 'MCP-MCP_Stop.mcr']
    profile = Path(os.environ['LOCALAPPDATA'])/'Autodesk/3dsMax'
    for year in range(2023, 2028):
        for folder in (profile/f'{year} - 64bit').glob('*/usermacros'):
            for name in retired:
                path = folder/name
                if path.exists():
                    preserve(path)
                    path.unlink()
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\Autodesk\3dsMax\{year-1998}.0') as key:
                maxdir = Path(winreg.QueryValueEx(key, 'Installdir')[0])
        except FileNotFoundError:
            continue
        for name in ('mcp_manager.ms', 'mcp_toolbar.ms'):
            path = maxdir/'scripts/mcp'/name
            if path.exists():
                preserve(path)
                path.unlink()

    config = Path(os.environ['LOCALAPPDATA'])/'3dsmax-mcp/mcp_config.ini'
    if config.exists():
        preserve(config)
        lines = config.read_text(encoding='utf-8-sig').splitlines()
        config.write_text('\n'.join(line for line in lines if not line.strip().startswith(('tcp_idle_poll_interval_ms','tcp_active_poll_interval_ms','tcp_active_poll_ticks_after_request'))) + '\n', encoding='utf-8')
    log('Native UI deployed; legacy slot and TCP macros retired. Restart Max to clear cached old macro definitions.')
    log(f'BACKUP {backup}')
    return backup


def main():
    with open(ROOT/'.native-ui-deployment.log', 'a', encoding='utf-8', buffering=1) as logfile:
        def log(message):
            print(message, file=logfile)
            print(message)
        try:
            deploy(log)
        except DeploymentError as exc:
            log(f'ABORTED {exc}')
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
