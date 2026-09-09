import asyncio
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from maxmcp.async_jobs import BLOCKED_COMMANDS, JobNotSentError, JobStore, bootstrap, is_provably_unsent
from maxmcp.tool_response import make_structured_tool, run_in_thread
from maxmcp.max_client import MaxClient, PipeNotConnectedError


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
        run_in_thread(slow)
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
        from maxmcp.tools import jobs as job_tools
        with patch('maxmcp.tools.jobs.client._config_dir',return_value=Path(self.tmp.name)), \
             patch('maxmcp.tools.jobs.client._resolve_pipe_name',return_value='pipe-A'), \
             patch('maxmcp.tools.jobs.client._probe_pipe_available',return_value=True):
            with self.assertRaisesRegex(ValueError,'safe mode'):
                job_tools.max_job_submit('hiddenDOSCommand "anything"')
            # max_job_render funnels through the same single check.
            with self.assertRaisesRegex(ValueError,'safe mode'):
                job_tools.max_job_render(output_path='c:/renders/deleteFile.png')


class SchedulingFailureTests(unittest.TestCase):
    """Only genuinely ambiguous scheduling failures may leave a job non-terminal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = JobStore(self.tmp.name, capacity=8)

    def submit(self, callback, target='pipe-A'):
        return self.store.submit('1+1', target, callback)['job_id']

    def settle(self, jid, expected):
        for _ in range(300):
            if self.store.status(jid)['state'] == expected:
                return
            time.sleep(.01)
        self.fail('job stayed in ' + self.store.status(jid)['state'])

    def raiser(self, exc):
        def schedule(script):
            raise exc
        return schedule

    def test_unsent_failures_are_terminal_and_release_the_instance(self):
        from maxmcp.async_jobs import busy_job
        # The type is the proof: max_client raises PipeNotConnectedError only at
        # sites that fire before the first WriteFile.
        for exc in (PipeNotConnectedError('Timed out waiting for the MCP connection lock; request not sent'),
                    PipeNotConnectedError('Named pipe pipe-A not found. Is the MCP Bridge plugin loaded in 3ds Max?'),
                    PipeNotConnectedError('Named pipe pipe-A disappeared while waiting.'),
                    PipeNotConnectedError('Timed out waiting for named pipe pipe-A after 30s.'),
                    JobNotSentError('probe said no')):
            jid = self.submit(self.raiser(exc))
            self.settle(jid, 'failed')
            with patch('maxmcp.async_jobs.jobs', self.store):
                self.assertIsNone(busy_job('pipe-A'))
            self.assertIn(str(exc)[:20], self.store.result(jid)['output'])
            self.store.forget(jid)

    def test_ambiguous_failures_stay_unknown_but_can_be_force_forgotten(self):
        jid = self.submit(self.raiser(TimeoutError('Timed out waiting for named pipe response after 30s.')))
        self.settle(jid, 'unknown')
        with self.assertRaisesRegex(ValueError, 'force=True'):
            self.store.forget(jid)
        # The target stays reserved until a human confirms Max is idle.
        with self.assertRaises(ValueError):
            self.submit(self.raiser(RuntimeError('x')))
        result = self.store.forget(jid, force=True)
        self.assertTrue(result['forced'])
        self.assertEqual(result['state_when_forgotten'], 'unknown')
        self.assertFalse((Path(self.tmp.name) / jid).exists())
        # Releasing the last uncertain job unwedges the instance for good.
        second = self.submit(self.raiser(RuntimeError('Scheduling was not acknowledged: {}')))
        self.settle(second, 'unknown')
        self.store.forget(second, force=True)

    def test_force_forget_refuses_a_job_that_is_actually_running(self):
        jid = self.submit(lambda script: {'result': 'bad'})
        (Path(self.tmp.name) / jid / 'state').write_text('running', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'cancellation is not completion'):
            self.store.forget(jid, force=True)

    def test_state_transitions_never_move_backwards(self):
        release = threading.Event()
        def slow(script):
            release.wait(2)
            return {'result': 'scheduled:' + script.split('return "scheduled:')[1].split('"')[0]}
        jid = self.store.submit('1+1', 'pipe-B', slow)['job_id']
        (Path(self.tmp.name) / jid / 'state').write_text('running', encoding='utf-8')
        self.assertEqual(self.store.status(jid)['state'], 'running')
        release.set()
        time.sleep(.3)
        # The late scheduler acknowledgement must not demote 'running' to 'scheduled'.
        self.assertEqual(self.store.status(jid)['state'], 'running')
        self.store._advance(jid, 'succeeded')
        self.store._advance(jid, 'failed')
        self.assertEqual(self.store.jobs[jid]['state'], 'succeeded')

    def test_unsent_is_classified_by_exception_type(self):
        # A pre-write failure is proven by its type, whatever the message says.
        self.assertTrue(is_provably_unsent(PipeNotConnectedError('anything at all')))
        self.assertTrue(is_provably_unsent(JobNotSentError('probe said no')))
        self.assertFalse(is_provably_unsent(ConnectionError('anything at all')))
        # A read timeout is never unsent, even though its text starts like the
        # pre-connect one ('timed out waiting for named pipe ...').
        self.assertFalse(is_provably_unsent(TimeoutError('Timed out waiting for named pipe response after 30s.')))

    def test_ambiguity_markers_win_over_unsent_markers(self):
        self.assertFalse(is_provably_unsent(RuntimeError('Scheduling was not acknowledged: {}')))
        self.assertFalse(is_provably_unsent(ConnectionError('Pipe closed while writing request.')))
        self.assertFalse(is_provably_unsent(TimeoutError('Timed out waiting for named pipe response after 30s.')))
        self.assertTrue(is_provably_unsent(ConnectionError('Failed to open pipe: Win32 error 5')))

    def test_safe_mode_is_enforced_by_the_store_itself(self):
        for token in BLOCKED_COMMANDS:
            with self.assertRaisesRegex(ValueError, 'safe mode'):
                self.store.submit('a ' + token.upper() + ' b', 'pipe-Z',
                                  lambda script: {'result': 'bad'}, config_dir=self.tmp.name)
        self.assertEqual(self.store.jobs, {})

    def test_safe_mode_off_lets_the_store_schedule_blocked_code(self):
        (Path(self.tmp.name) / 'mcp_config.ini').write_text('[mcp]\nsafe_mode = false\n', encoding='utf-8')
        jid = self.store.submit('deleteFile "x"', 'pipe-Y', lambda script: {'result': 'bad'},
                                config_dir=self.tmp.name)['job_id']
        self.assertIn(jid, self.store.jobs)

    def test_native_blocklist_matches_the_cpp_dispatcher(self):
        source = (Path(__file__).resolve().parents[1] / 'native/src/command_dispatcher.cpp').read_text(encoding='utf-8')
        block = source.split('static const char* blocked[]')[1].split('};')[0]
        self.assertEqual([line.strip().strip('",') for line in block.splitlines() if '"' in line],
                         list(BLOCKED_COMMANDS))

    def test_per_process_root_is_removed_at_exit_when_empty(self):
        store = JobStore(str(Path(self.tmp.name) / 'sub'))
        store.root.mkdir()
        (store.root / 'leftover').write_text('x', encoding='utf-8')
        store._remove_root_if_empty()
        self.assertTrue(store.root.exists())
        (store.root / 'leftover').unlink()
        store._remove_root_if_empty()
        self.assertFalse(store.root.exists())

    def test_default_store_registers_its_scratch_dir_for_cleanup(self):
        with patch('maxmcp.async_jobs.atexit.register') as register:
            store = JobStore()
        register.assert_called_once_with(store._remove_root_if_empty)
        self.assertFalse(store.root.exists())



if __name__ == '__main__': unittest.main()
