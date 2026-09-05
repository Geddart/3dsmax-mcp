import json
import unittest
from unittest.mock import patch
from maxmcp.max_client import MaxClient, MaxClientManager
from maxmcp.tools import fork_workflows, fork_snapshots

class ForkCompatibilityTests(unittest.TestCase):
    def test_default_routing_uses_upstream_instance_discovery(self):
        client=MaxClientManager()
        with patch.object(MaxClient,'send_command',return_value={'result':'ok'}) as send:
            self.assertEqual(client.send_command('1')['result'],'ok')
            send.assert_called_once_with('1',cmd_type='maxscript',timeout=None)

    def test_explicit_legacy_slot_uses_tcp_not_an_unrelated_native_pipe(self):
        client=MaxClientManager()
        slot=client._slot_client(2)
        self.assertEqual(slot.port,8766)
        self.assertEqual(slot.transport,'tcp')

    def test_discovered_slot_is_bound_to_its_native_pipe(self):
        client=MaxClientManager()
        client._slot_pipes[2]=r'\\.\pipe\3dsmax-mcp-pid-42'
        slot=client._slot_client(2)
        self.assertEqual(slot.transport,'pipe')
        self.assertEqual(slot.pipe_name,r'\\.\pipe\3dsmax-mcp-pid-42')

    def test_invalid_slot_is_rejected(self):
        with self.assertRaises(ValueError): MaxClientManager()._slot_client(0)

    def test_old_verified_material_tool_uses_supported_fallback(self):
        with patch.object(fork_workflows.client,'send_command',side_effect=AssertionError('must not call removed native handler')), patch('maxmcp.tools.material_ops.get_material_slots',return_value='{}'), patch('maxmcp.tools.material_ops.set_material_properties',return_value='ok'), patch('maxmcp.tools.fork_snapshots.get_scene_delta',return_value='{}'), patch('maxmcp.tools.inspect.inspect_object',return_value='{}'):
            self.assertIsInstance(json.loads(fork_workflows.set_material_verified('Box',{'roughness':'0.5'})),dict)

if __name__=='__main__': unittest.main()
