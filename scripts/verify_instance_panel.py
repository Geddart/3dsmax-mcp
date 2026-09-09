"""Load and verify the native-only instance panel in an explicitly selected Max."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maxmcp.max_client import MaxClientManager
from maxmcp.tools.max_ui import max_ui_windows, max_ui_capture

target=int(sys.argv[1])
c=MaxClientManager()
c.select_instance(f'pid-{target}')
script=(Path(__file__).resolve().parents[1]/'maxscript/mcp_server.ms').as_posix()
print(c.send_command(f'fileIn "{script}"; "loaded"'),flush=True)
print(c.send_command('try(destroyDialog MCP_InstancePanel)catch(); createDialog MCP_InstancePanel; MCP_InstancePanel.targets.items as string'),flush=True)
print(c.send_command('MCP_Server.escapeJsonString "native helper retained"'),flush=True)
window=next(w['token'] for w in max_ui_windows(target)['windows'] if w['title']=='MCP Native Instances')
print(max_ui_capture(target,window),flush=True)
