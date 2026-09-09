import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from maxmcp import max_ui as max_ui_core
from maxmcp.max_ui import UITargetError, request, resolve_pid
from maxmcp.tools import max_ui

NOTEPAD = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'notepad.exe'


@contextmanager
def registered(*pids, denied=()):
    """Pretend the native bridge advertises exactly these live instances."""
    with patch('maxmcp.max_ui.registered_pids', return_value=set(pids)), \
         patch('maxmcp.max_ui.denied_pids', return_value=set(denied)):
        yield


class FakeClient:
    def __init__(self, pid):
        self._pid = pid

    def selected_pid(self):
        return self._pid


class MaxUITests(unittest.TestCase):
    def test_explicit_pid_required(self):
        for pid in (0, -1, '42'):
            with self.assertRaises(ValueError): request('windows', pid)

    def test_values_are_json_stdin_not_shell_code(self):
        value = '"; Start-Process cmd; $(anything)'
        with registered(42), patch('maxmcp.max_ui.subprocess.run',
                                   return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
            request('set_value', 42, value=value)
            args, kwargs = run.call_args
            self.assertNotIn(value, ' '.join(args[0]))
            self.assertEqual(json.loads(kwargs['input'])['value'], value)
            self.assertFalse(kwargs.get('shell', False))
            self.assertGreater(kwargs['timeout'], 0)
            self.assertIn('Bypass', args[0])

    def test_timeout_is_unknown_outcome_and_never_retried(self):
        with registered(42), patch('maxmcp.max_ui.subprocess.run',
                                   side_effect=subprocess.TimeoutExpired('uia', 12)) as run:
            with self.assertRaisesRegex(RuntimeError, 'outcome is unknown'): request('invoke', 42)
            self.assertEqual(run.call_count, 1)

    def test_inspection_and_wait_bounds(self):
        with self.assertRaises(ValueError): max_ui.max_ui_inspect(42, {}, max_elements=5000)
        with self.assertRaises(ValueError): max_ui.max_ui_wait(42, 'test', 31)
        with self.assertRaises(ValueError): max_ui.max_ui_wait(42, 'test', 1, match='regex')
        with self.assertRaises(ValueError): max_ui.max_ui_send_keys(42, {}, '')
        with self.assertRaises(ValueError): max_ui.max_ui_inspect(42)
        with self.assertRaises(ValueError): max_ui.max_ui_capture(42)
        with self.assertRaises(ValueError): max_ui.max_ui_invoke(42)

    def test_nul_value_is_rejected_before_mutation(self):
        with patch('maxmcp.tools.max_ui.request') as write:
            with self.assertRaises(ValueError): max_ui.max_ui_set_value(42, {}, 'a\x00b')
            write.assert_not_called()

    def test_grouped_and_mixed_case_global_shortcuts_rejected(self):
        with patch('maxmcp.tools.max_ui.request') as send:
            for keys in ('%({TAB})', '%{tab}', '^+{ESC}', '^({esc})', '{LWIN}'):
                with self.assertRaises(ValueError): max_ui.max_ui_send_keys(42, {}, keys)
            send.assert_not_called()


class MaxUITargetBindingTests(unittest.TestCase):
    """A wrong PID would drive somebody's production Max, so binding fails closed."""

    def test_omitted_pid_uses_the_session_instance(self):
        with patch('maxmcp.max_ui._session_client', return_value=FakeClient(4321)), \
             patch('maxmcp.max_ui.denied_pids', return_value=set()), \
             patch('maxmcp.max_ui.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 0, '{"windows":[]}', '')) as run:
            answer = request('windows')
            self.assertEqual(json.loads(run.call_args.kwargs['input'])['process_id'], 4321)
            self.assertEqual(answer['pid'], 4321)

    def test_unbound_session_refuses_instead_of_guessing(self):
        with patch('maxmcp.max_ui._session_client', return_value=FakeClient(None)), \
             patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'No 3ds Max instance is bound'): request('windows')
            run.assert_not_called()

    def test_missing_selected_pid_support_is_reported_clearly(self):
        with patch('maxmcp.max_ui._session_client', return_value=object()), \
             patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'selected_pid'): request('windows')
            run.assert_not_called()

    def test_explicit_pid_must_be_a_registered_live_instance(self):
        with registered(4321), patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'not a live registered'): request('invoke', 999)
            run.assert_not_called()
            self.assertEqual(resolve_pid(4321), 4321)

    def test_denied_pid_is_refused_before_powershell_starts(self):
        with registered(4321, denied=(4321,)), patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'protected'): request('invoke', 4321)
            run.assert_not_called()
        with patch('maxmcp.max_ui._session_client', return_value=FakeClient(4321)), \
             patch('maxmcp.max_ui.denied_pids', return_value={4321}), \
             patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'protected'): request('windows')
            run.assert_not_called()

    def test_deny_list_sources(self):
        with patch.dict(os.environ, {max_ui_core.DENY_ENV: '11, 12;13,bogus'}, clear=False), \
             patch('maxmcp.pid_fence.config_dir', return_value=Path(tempfile.gettempdir()) / 'absent-3dsmax-mcp'):
            self.assertEqual(max_ui_core.denied_pids(), {11, 12, 13})
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / max_ui_core.PROTECTED_FILE).write_text(json.dumps({'pids': [77, '78']}), encoding='utf-8')
        environment = {key: value for key, value in os.environ.items() if key != max_ui_core.DENY_ENV}
        with patch.dict(os.environ, environment, clear=True), \
             patch('maxmcp.pid_fence.config_dir', return_value=directory):
            self.assertEqual(max_ui_core.denied_pids(), {77, 78})

    def test_max_version_fence_refuses_a_restarted_max(self):
        """A recycled PID lapses the fence; the bridge's max_version does not."""
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        instances = directory / 'instances'
        instances.mkdir()
        (instances / 'pid-4312.json').write_text(
            json.dumps({'pid': 4312, 'pipe': 'x', 'max_version': 27000}), encoding='utf-8')
        (directory / max_ui_core.PROTECTED_FILE).write_text(
            json.dumps({'max_versions': [27000]}), encoding='utf-8')
        with patch('maxmcp.max_ui.config_dir', return_value=directory), \
             patch('maxmcp.pid_fence.config_dir', return_value=directory), \
             patch('maxmcp.max_ui._process_is_live', return_value=True), \
             patch('maxmcp.max_ui.subprocess.run') as run:
            with self.assertRaisesRegex(UITargetError, 'protected'):
                request('invoke', 4312)
            run.assert_not_called()

    def test_registry_only_reports_live_recorded_instances(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        instances = directory / 'instances'
        instances.mkdir()
        (instances / 'pid-999999.json').write_text(json.dumps({'pid': 999999, 'pipe': 'x'}), encoding='utf-8')
        (instances / 'pid-broken.json').write_text('{not json', encoding='utf-8')
        with patch('maxmcp.max_ui.config_dir', return_value=directory):
            self.assertEqual(max_ui_core.registered_pids(), set())
            with patch('maxmcp.max_ui._process_is_live', return_value=True):
                self.assertEqual(max_ui_core.registered_pids(), {999999})


class MaxUIResultShapeTests(unittest.TestCase):
    def test_set_value_reports_normalised_readback_without_failing(self):
        provider = json.dumps({'action': 'set_value', 'completed': True, 'value_written': '1',
                               'readback': '1.0', 'matches': False, 'value': '1.0'})
        with registered(42), patch('maxmcp.max_ui.subprocess.run',
                                   return_value=subprocess.CompletedProcess([], 0, provider, '')) as run:
            answer = max_ui.max_ui_set_value(42, {'hwnd': '1'}, '1', commit=True)
            self.assertEqual((answer['value_written'], answer['readback'], answer['matches']), ('1', '1.0', False))
            self.assertTrue(answer['completed'])
            self.assertEqual(answer['pid'], 42)
            self.assertIs(json.loads(run.call_args.kwargs['input'])['commit'], True)

    def test_every_result_names_the_targeted_pid(self):
        with registered(42), patch('maxmcp.max_ui.subprocess.run',
                                   return_value=subprocess.CompletedProcess([], 0, '{"windows":[]}', '')):
            self.assertEqual(max_ui.max_ui_windows(42)['pid'], 42)


class MaxUIWaitTests(unittest.TestCase):
    @staticmethod
    def _windows(*titles):
        return {'windows': [{'title': title, 'token': {}} for title in titles], 'pid': 42}

    def test_exact_match_normalises_trailing_marker_and_whitespace(self):
        with registered(42), patch('maxmcp.tools.max_ui.request',
                                   return_value=self._windows('Render Setup *')) as read:
            found = max_ui.max_ui_wait(42, ' Render Setup ', 2)
            self.assertFalse(found['timed_out'])
            self.assertEqual(found['pid'], 42)
            self.assertEqual(read.call_count, 1)

    def test_contains_match_is_opt_in_and_case_insensitive(self):
        with registered(42), patch('maxmcp.tools.max_ui.request', return_value=self._windows('Render Setup')):
            self.assertTrue(max_ui.max_ui_wait(42, 'render', 0)['timed_out'])
            self.assertFalse(max_ui.max_ui_wait(42, 'render', 0, match='contains')['timed_out'])

    def test_zero_timeout_still_probes_once(self):
        with registered(42), patch('maxmcp.tools.max_ui.request', return_value=self._windows()) as read:
            answer = max_ui.max_ui_wait(42, 'absent', 0)
            self.assertTrue(answer['timed_out'])
            self.assertEqual(answer['pid'], 42)
            self.assertEqual(read.call_count, 1)

    def test_short_waits_still_give_the_provider_time_to_answer(self):
        with registered(42), patch('maxmcp.tools.max_ui.request', return_value=self._windows()) as read:
            max_ui.max_ui_wait(42, 'absent', .01)
            self.assertGreaterEqual(read.call_args.kwargs['timeout'], 4)

    def test_provider_timeout_is_reported_not_raised(self):
        from maxmcp.max_ui import UIReadTimeout
        with registered(42), patch('maxmcp.tools.max_ui.request', side_effect=UIReadTimeout):
            self.assertTrue(max_ui.max_ui_wait(42, 'absent', .01)['timed_out'])


@unittest.skipUnless(os.name == 'nt' and NOTEPAD.exists(), 'needs Windows PowerShell and notepad.exe')
class MaxUIRealProviderTests(unittest.TestCase):
    """One end-to-end run of the real helper, against a process we own."""

    def test_helper_refuses_a_process_that_is_not_3dsmax(self):
        try:
            notepad = subprocess.Popen([str(NOTEPAD)])
        except OSError as exc:
            self.skipTest(f'notepad.exe could not be started: {exc}')
        try:
            for _ in range(20):
                if notepad.poll() is not None:
                    self.skipTest('notepad.exe exited immediately (Store app launcher)')
                time.sleep(.1)
            directory = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, directory, True)
            (directory / 'instances').mkdir()
            (directory / 'instances' / f'pid-{notepad.pid}.json').write_text(
                json.dumps({'pid': notepad.pid, 'pipe': f'\\\\.\\pipe\\3dsmax-mcp-{notepad.pid}'}), encoding='utf-8')
            with patch('maxmcp.max_ui.config_dir', return_value=directory):
                # The record is live, so binding succeeds and the helper itself refuses.
                self.assertEqual(max_ui_core.registered_pids(), {notepad.pid})
                with self.assertRaisesRegex(RuntimeError, 'Target must be 3dsmax.exe'):
                    request('windows', notepad.pid, timeout=60)
        finally:
            notepad.kill()
            notepad.wait(timeout=10)
        with patch('maxmcp.max_ui.config_dir', return_value=directory):
            self.assertEqual(max_ui_core.registered_pids(), set())


if __name__ == '__main__': unittest.main()
