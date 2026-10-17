import json
import unittest
from unittest.mock import patch
from maxmcp.max_client import MaxClient, MaxClientManager
from maxmcp.tools import fork_workflows

class ForkCompatibilityTests(unittest.TestCase):
    def test_native_selection_has_no_fixed_slot_count(self):
        client=MaxClientManager()
        records=[{'instance_id':f'pid-{i}', 'pid':i, 'pipe':fr'\\.\pipe\3dsmax-mcp-pid-{i}'} for i in range(1,6)]
        with patch.object(client,'_live_instances',return_value=records), patch.object(client,'_active_instance',return_value=None), patch('maxmcp.max_client._process_alive',return_value=True), patch.object(client,'_probe_pipe_available',return_value=True):
            self.assertEqual(len(client.list_max_instances()['instances']),5)
            self.assertEqual(client.select_max_instance(5)['target_pid'],5)
            self.assertEqual(client.selected_pid(),5)
            client.release_max_instance()
            self.assertIsNone(client._bound_target)

    def test_explicit_tcp_is_rejected(self):
        with self.assertRaises(ValueError): MaxClient(transport='tcp')

    def test_disappeared_target_is_not_reassigned(self):
        client=MaxClientManager()
        with patch.object(client,'_live_instances',return_value=[]), patch('maxmcp.max_client._process_alive',return_value=False):
            with self.assertRaises(ConnectionError): client.select_max_instance(42)

    def test_old_verified_material_tool_uses_supported_fallback(self):
        with patch.object(fork_workflows.client,'send_command',side_effect=AssertionError('must not call removed native handler')), patch('maxmcp.tools.material_ops.get_material_slots',return_value='{}'), patch('maxmcp.tools.material_ops.set_material_properties',return_value='ok'), patch('maxmcp.tools.fork_snapshots.get_scene_delta',return_value='{}'), patch('maxmcp.tools.inspect.inspect_object',return_value='{}'):
            self.assertIsInstance(json.loads(fork_workflows.set_material_verified('Box',{'roughness':'0.5'})),dict)
