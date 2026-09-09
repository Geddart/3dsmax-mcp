"""Real MCP catalog/async acceptance; optional PID runs a short read-only job."""
import ast
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import tomllib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
def payload(result):
    data=result.structuredContent or json.loads(result.content[0].text)
    assert data.get('ok'), data
    return data['result']

async def check(profile, pid=None):
    if profile == 'configured':
        settings=tomllib.loads((Path.home()/'.codex/config.toml').read_text(encoding='utf-8-sig'))['mcp_servers']['3dsmax-mcp']
        assert settings['env']['MCP_TOOL_PROFILE']=='progressive'
        params=StdioServerParameters(command=settings['command'],args=settings.get('args',[]),env={**os.environ,**settings.get('env',{})})
    else:
        params=StdioServerParameters(command=str(ROOT/'.venv/Scripts/3dsmax-mcp.exe'),env={**os.environ,'MCP_TOOL_PROFILE':profile})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            catalog=await session.list_tools()
            names={tool.name for tool in catalog.tools}
            schema_bytes=len(catalog.model_dump_json().encode('utf-8'))
            if profile=='full':
                old=set()
                for file in (ROOT.parents[1]/'src/tools').glob('*.py'):
                    for node in ast.walk(ast.parse(file.read_text(encoding='utf-8-sig'))):
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='tool' for d in node.decorator_list):
                            old.add(node.name)
                assert old and not old-names, old-names
                print('FULL',len(names),'LEGACY_NAMES_RETAINED',len(old),flush=True)
                if pid:
                    payload(await session.call_tool('select_max_instance',{'pid':pid}))
                    job=payload(await session.call_tool('max_job_submit',{'code':'sleep 2; "MCP async verified"'}))
                    wait=asyncio.create_task(session.call_tool('max_job_wait',{'job_id':job['job_id'],'timeout_seconds':10}))
                    await asyncio.sleep(.1)
                    start=time.monotonic()
                    payload(await session.call_tool('max_job_list',{}))
                    assert time.monotonic()-start < 1, 'MCP event loop blocked by wait'
                    assert payload(await wait)['state']=='succeeded'
                    assert payload(await session.call_tool('max_job_result',{'job_id':job['job_id']}))['output']=='MCP async verified'
                    print('LIVE_MCP_ASYNC_PASS',flush=True)
            else:
                assert names=={'list_toolsets','describe_toolset','call_tool'}
                groups=payload(await session.call_tool('list_toolsets',{}))
                operational={}
                for group in groups['toolsets']:
                    described=payload(await session.call_tool('describe_toolset',{'toolset':group['name']}))
                    assert described['tools']
                    for tool in described['tools']:
                        assert tool['name'] not in operational, tool['name']
                        operational[tool['name']]=tool['input_schema']
                assert len(operational)==groups['tool_count']
                assert {tool.name for tool in (await session.list_tools()).tools}==names
                payload(await session.call_tool('call_tool',{'name':'max_job_list','arguments':{}}))
                if pid:
                    payload(await session.call_tool('call_tool',{'name':'select_max_instance','arguments':{'pid':pid}}))
                    job=payload(await session.call_tool('call_tool',{'name':'max_job_submit','arguments':{'code':'sleep 1; "progressive verified"'}}))
                    done=payload(await session.call_tool('call_tool',{'name':'max_job_wait','arguments':{'job_id':job['job_id'],'timeout_seconds':10}}))
                    assert done['state']=='succeeded', done
                print('PROGRESSIVE_PASS',len(operational),'OPERATIONS',len(groups['toolsets']),'GROUPS',flush=True)
            return schema_bytes, ({tool.name:tool.inputSchema for tool in catalog.tools} if profile=='full' else operational)

async def main():
    pid=int(sys.argv[1]) if len(sys.argv)>1 else None
    full, full_schemas=await check('full',pid)
    progressive, progressive_schemas=await check('configured',pid)
    assert full_schemas==progressive_schemas, 'Progressive schemas differ from full profile'
    print('SCHEMA_BYTES', {'full':full,'progressive':progressive,'reduction_percent':round(100*(1-progressive/full),2)},flush=True)

asyncio.run(main())
