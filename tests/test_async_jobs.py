import asyncio
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from maxmcp.async_jobs import JobStore, bootstrap
from maxmcp.tool_response import make_structured_tool
from maxmcp.max_client import MaxClient


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = JobStore(self.tmp.name, capacity=2)

    def submit(self, callback=None):
        return self.store.submit('1+1', 'pipe-A', callback or (lambda script: {'result': 'bad'}))

    def test_submit_and_poll_do_not_wait_for_blocked_max(self):
        release = threading.Event()
        started = threading.Event()
        def block(script):
            started.set()
            release.wait(2)
            return {'result': 'bad'}
        started_at = time.monotonic()
        result = self.submit(block)
        self.assertLess(time.monotonic()-started_at, .5)
        self.assertTrue(started.wait(1))
        jid = result['job_id']
        self.assertEqual(self.store.status(jid)['state'], 'submitting')
        self.assertTrue(self.store.cancel(jid)['cancel_requested'])
        self.assertNotEqual(self.store.status(jid)['state'], 'cancelled')
        with self.assertRaises(ValueError): self.submit()
        with self.assertRaises(ValueError): self.store.forget(jid)
        release.set()

    def test_completed_files_override_uncertain_schedule_and_paginate(self):
        result = self.submit()
        jid = result['job_id']; folder = Path(self.tmp.name)/jid
        (folder/'result').write_text('abcdef', encoding='utf-8')
        (folder/'state').write_text('succeeded', encoding='utf-8')
        self.assertEqual(self.store.result(jid, 2, 2)['output'], 'cd')
        self.assertEqual(self.store.result(jid, 2, 2)['next_offset'], 4)
        self.store.forget(jid)
        self.assertFalse(folder.exists())

    def test_foreign_handles_and_invalid_pagination_rejected(self):
        with self.assertRaises(ValueError): self.store.status('../other')
        with self.assertRaises(ValueError): self.store.result('anything', -1)

    def test_terminal_status_is_latched_and_elapsed_time_stops(self):
        item = self.submit(); jid = item['job_id']; folder = Path(self.tmp.name)/jid
        (folder/'state').write_text('succeeded', encoding='utf-8')
        first = self.store.status(jid)
        (folder/'state').unlink()
        time.sleep(.02)
        second = self.store.status(jid)
        self.assertEqual(second['state'], 'succeeded')
        self.assertEqual(first['elapsed_seconds'], second['elapsed_seconds'])

    def test_nonfinite_progress_and_transient_sharing_violation(self):
        item = self.submit(); jid = item['job_id']; folder = Path(self.tmp.name)/jid
        for value in ('NaN', 'Infinity', '-Infinity'):
            (folder/'progress').write_text(value, encoding='utf-8')
            self.assertNotIn('progress_percent', self.store.status(jid))
        with patch.object(Path, 'read_text', side_effect=PermissionError('writer holds file')):
            self.assertEqual(self.store.status(jid)['job_id'], jid)

    def test_explicit_rejection_releases_target_and_can_be_forgotten(self):
        def reject(script):
            import re
            jid = re.search('scheduled:([a-f0-9]+)', script).group(1)
            return {'result': 'rejected:' + jid + ':busy'}
        item = self.submit(reject); jid = item['job_id']
        for _ in range(100):
            if self.store.status(jid)['state'] == 'failed': break
            time.sleep(.01)
        self.assertEqual(self.store.status(jid)['state'], 'failed')
        self.store.forget(jid)

    def test_bootstrap_stops_timer_before_operation_and_is_idempotent(self):
        text = bootstrap('abc', Path(self.tmp.name))
        self.assertLess(text.index('sender.Stop()'), text.index('local answer = execute'))
        self.assertIn('/accepted', text)
        self.assertIn('mcpAsyncActiveJob', text)

    def test_async_wait_does_not_block_other_mcp_calls(self):
        def slow():
            time.sleep(.15)
            return {'value': 1}
        slow.__module__ = 'maxmcp.tools.jobs'
        wrapped = make_structured_tool(slow)
        async def check():
            task = asyncio.create_task(wrapped())
            await asyncio.sleep(.02)
            self.assertFalse(task.done())
            self.assertTrue((await task)['ok'])
        asyncio.run(check())

    def test_busy_job_blocks_normal_bridge_call_before_sending(self):
        client = MaxClient(transport='pipe', pipe_name='pipe-A')
        with patch('maxmcp.async_jobs.busy_job', return_value='job42'), patch.object(client, '_send_via_pipe') as send:
            with self.assertRaisesRegex(RuntimeError, 'job42'): client.send_command('delete objects')
            send.assert_not_called()

    def test_existing_render_abort_remains_available_while_job_is_busy(self):
        client = MaxClient(transport='pipe', pipe_name='pipe-A')
        with patch('maxmcp.async_jobs.busy_job', return_value='job42'), patch.object(client, '_send_via_pipe', return_value=b'{"success":true,"result":"ok"}') as send:
            self.assertEqual(client.send_command('{}',cmd_type='native:render_cancel')['result'],'ok')
            send.assert_called_once()

    def test_job_respects_native_safe_mode_blocklist(self):
        from maxmcp.tools.jobs import max_job_submit
        with patch('maxmcp.tools.jobs.client._config_dir',return_value=Path(self.tmp.name)):
            with self.assertRaisesRegex(ValueError,'safe mode'):
                max_job_submit('hiddenDOSCommand "anything"')


if __name__ == '__main__': unittest.main()
