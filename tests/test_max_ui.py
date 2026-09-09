import json
import subprocess
import unittest
from unittest.mock import patch
from maxmcp.max_ui import request
from maxmcp.tools import max_ui


class MaxUITests(unittest.TestCase):
    def test_explicit_pid_required(self):
        for pid in (0, -1, '42'):
            with self.assertRaises(ValueError): request('windows', pid)

    def test_values_are_json_stdin_not_shell_code(self):
        value = '"; Start-Process cmd; $(anything)'
        with patch('maxmcp.max_ui.subprocess.run', return_value=subprocess.CompletedProcess([],0,'{}','')) as run:
            request('set_value', 42, value=value)
            args, kwargs = run.call_args
            self.assertNotIn(value, ' '.join(args[0]))
            self.assertEqual(json.loads(kwargs['input'])['value'], value)
            self.assertFalse(kwargs.get('shell', False))
            self.assertGreater(kwargs['timeout'], 0)

    def test_timeout_is_unknown_outcome_and_never_retried(self):
        with patch('maxmcp.max_ui.subprocess.run', side_effect=subprocess.TimeoutExpired('uia',12)) as run:
            with self.assertRaisesRegex(RuntimeError, 'outcome is unknown'): request('invoke',42)
            self.assertEqual(run.call_count,1)

    def test_inspection_and_wait_bounds(self):
        with self.assertRaises(ValueError): max_ui.max_ui_inspect(42,{},max_elements=5000)
        with self.assertRaises(ValueError): max_ui.max_ui_wait(42,'test',31)
        with self.assertRaises(ValueError): max_ui.max_ui_send_keys(42,{},'')

    def test_wait_limits_provider_time_and_handles_timeout(self):
        from maxmcp.max_ui import UIReadTimeout
        with patch('maxmcp.tools.max_ui.request', side_effect=UIReadTimeout) as read:
            self.assertTrue(max_ui.max_ui_wait(42, 'absent', .01)['timed_out'])
            self.assertLessEqual(read.call_args.kwargs['timeout'], .010001)
        with patch('maxmcp.tools.max_ui.request') as read:
            self.assertTrue(max_ui.max_ui_wait(42, 'absent', 0)['timed_out'])
            read.assert_not_called()

    def test_nul_value_is_rejected_before_mutation(self):
        with patch('maxmcp.tools.max_ui.request') as write:
            with self.assertRaises(ValueError): max_ui.max_ui_set_value(42, {}, 'a\x00b')
            write.assert_not_called()

    def test_grouped_and_mixed_case_global_shortcuts_rejected(self):
        with patch('maxmcp.tools.max_ui.request') as send:
            for keys in ('%({TAB})', '%{tab}', '^+{ESC}', '^({esc})', '{LWIN}'):
                with self.assertRaises(ValueError): max_ui.max_ui_send_keys(42, {}, keys)
            send.assert_not_called()


if __name__ == '__main__': unittest.main()
