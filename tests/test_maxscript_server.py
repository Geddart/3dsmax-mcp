from pathlib import Path
import unittest

class NativeScriptTests(unittest.TestCase):
    def test_helpers_remain_without_listener_or_slot_ui(self):
        script=(Path(__file__).parents[1]/'maxscript/mcp_server.ms').read_text(encoding='utf-8-sig')
        self.assertIn('fn escapeJsonString',script)
        self.assertIn('MCP_InstancePanel',script)
        self.assertNotIn('TcpListener',script)
        self.assertNotIn('MCP_StartSlot',script)
