"""Real MCP catalog/async acceptance; optional PID runs a short read-only job.

Everything environment-specific is parametrized. Defaults are derived from the
repository itself, so a fresh clone needs no editing:

    uv run python scripts/verify_feature_catalog.py                 # catalog only
    uv run python scripts/verify_feature_catalog.py --pid 12345     # + live Max job
    uv run python scripts/verify_feature_catalog.py --legacy-ref v0.5.3-fork

Overrides (flag, then environment variable):
    --server-command / MCP_VERIFY_SERVER_COMMAND  server executable
    --codex-config   / MCP_VERIFY_CODEX_CONFIG    codex config.toml with the MCP entry
    --server-name    / MCP_VERIFY_SERVER_NAME     mcp_servers key inside that config
    --legacy-ref     / MCP_VERIFY_LEGACY_REF      git ref holding the pre-fork tool layout
    --legacy-path    / MCP_VERIFY_LEGACY_PATH     tools package path inside that ref
"""
import argparse
import ast
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
OPTS = argparse.Namespace()


def default_server_command():
    for candidate in (ROOT / '.venv/Scripts/3dsmax-mcp.exe', ROOT / '.venv/bin/3dsmax-mcp'):
        if candidate.exists():
            return str(candidate)
    return shutil.which('3dsmax-mcp') or str(ROOT / '.venv/Scripts/3dsmax-mcp.exe')


def legacy_tool_names(ref, path):
    """Read the pre-fork tool modules out of a git ref - no sibling checkout needed."""
    listing = subprocess.run(['git', '-C', str(ROOT), 'ls-tree', '--name-only', f'{ref}:{path}'],
                             capture_output=True, text=True, check=True).stdout.split()
    names = set()
    for entry in listing:
        if not entry.endswith('.py'):
            continue
        source = subprocess.run(['git', '-C', str(ROOT), 'show', f'{ref}:{path}/{entry}'],
                                capture_output=True, text=True, check=True).stdout
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'tool'
                for d in node.decorator_list
            ):
                names.add(node.name)
    return names


def payload(result):
    data = result.structuredContent or json.loads(result.content[0].text)
    assert data.get('ok'), data
    return data['result']


async def check(profile, pid=None):
    if profile == 'configured':
        config = tomllib.loads(Path(OPTS.codex_config).expanduser().read_text(encoding='utf-8-sig'))
        settings = config['mcp_servers'][OPTS.server_name]
        assert settings['env']['MCP_TOOL_PROFILE'] == 'progressive'
        params = StdioServerParameters(command=settings['command'], args=settings.get('args', []), env={**os.environ, **settings.get('env', {})})
    else:
        params = StdioServerParameters(command=OPTS.server_command, env={**os.environ, 'MCP_TOOL_PROFILE': profile})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            names = {tool.name for tool in catalog.tools}
            schema_bytes = len(catalog.model_dump_json().encode('utf-8'))
            if profile == 'full':
                old = legacy_tool_names(OPTS.legacy_ref, OPTS.legacy_path)
                assert old and not old - names, old - names
                print('FULL', len(names), 'LEGACY_NAMES_RETAINED', len(old), flush=True)
                if pid:
                    payload(await session.call_tool('set_active_instance', {'instance_id': f'pid-{pid}'}))
                    job = payload(await session.call_tool('max_job_submit', {'code': 'sleep 2; "MCP async verified"'}))
                    wait = asyncio.create_task(session.call_tool('max_job_wait', {'job_id': job['job_id'], 'timeout_seconds': 10}))
                    await asyncio.sleep(.1)
                    start = time.monotonic()
                    payload(await session.call_tool('max_job_list', {}))
                    assert time.monotonic() - start < 1, 'MCP event loop blocked by wait'
                    assert payload(await wait)['state'] == 'succeeded'
                    assert payload(await session.call_tool('max_job_result', {'job_id': job['job_id']}))['output'] == 'MCP async verified'
                    print('LIVE_MCP_ASYNC_PASS', flush=True)
            else:
                assert names == {'list_toolsets', 'describe_toolset', 'call_tool'}
                groups = payload(await session.call_tool('list_toolsets', {}))
                operational = {}
                for group in groups['toolsets']:
                    described = payload(await session.call_tool('describe_toolset', {'toolset': group['name']}))
                    assert described['tools']
                    for tool in described['tools']:
                        assert tool['name'] not in operational, tool['name']
                        operational[tool['name']] = tool['input_schema']
                assert len(operational) == groups['tool_count']
                assert {tool.name for tool in (await session.list_tools()).tools} == names
                payload(await session.call_tool('call_tool', {'name': 'max_job_list', 'arguments': {}}))
                if pid:
                    payload(await session.call_tool('call_tool', {'name': 'set_active_instance', 'arguments': {'instance_id': f'pid-{pid}'}}))
                    job = payload(await session.call_tool('call_tool', {'name': 'max_job_submit', 'arguments': {'code': 'sleep 1; "progressive verified"'}}))
                    done = payload(await session.call_tool('call_tool', {'name': 'max_job_wait', 'arguments': {'job_id': job['job_id'], 'timeout_seconds': 10}}))
                    assert done['state'] == 'succeeded', done
                print('PROGRESSIVE_PASS', len(operational), 'OPERATIONS', len(groups['toolsets']), 'GROUPS', flush=True)
            return schema_bytes, ({tool.name: tool.inputSchema for tool in catalog.tools} if profile == 'full' else operational)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pid', nargs='?', type=int, default=None, help='3ds Max PID for the optional live job checks')
    parser.add_argument('--pid', dest='pid_opt', type=int, default=None, help='same as the positional PID')
    parser.add_argument('--server-command', default=os.environ.get('MCP_VERIFY_SERVER_COMMAND') or default_server_command(),
                        help='server executable used for the non-configured profiles')
    parser.add_argument('--codex-config', default=os.environ.get('MCP_VERIFY_CODEX_CONFIG') or str(Path.home() / '.codex/config.toml'),
                        help='TOML file holding the configured MCP server entry')
    parser.add_argument('--server-name', default=os.environ.get('MCP_VERIFY_SERVER_NAME', '3dsmax-mcp'),
                        help='key under [mcp_servers] in that config')
    parser.add_argument('--legacy-ref', default=os.environ.get('MCP_VERIFY_LEGACY_REF', 'master'),
                        help='git ref carrying the pre-fork tool layout (default: master)')
    parser.add_argument('--legacy-path', default=os.environ.get('MCP_VERIFY_LEGACY_PATH', 'src/tools'),
                        help='tools package path inside that ref')
    opts = parser.parse_args(argv)
    opts.pid = opts.pid_opt if opts.pid_opt is not None else opts.pid
    return opts


async def main(pid):
    full, full_schemas = await check('full', pid)
    progressive, progressive_schemas = await check('configured', pid)
    assert full_schemas == progressive_schemas, 'Progressive schemas differ from full profile'
    print('SCHEMA_BYTES', {'full': full, 'progressive': progressive, 'reduction_percent': round(100 * (1 - progressive / full), 2)}, flush=True)


if __name__ == '__main__':
    OPTS = parse_args(sys.argv[1:])
    asyncio.run(main(OPTS.pid))
