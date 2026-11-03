import unittest
from unittest.mock import patch
from network_config import public_base, sharing_config

class NetworkTests(unittest.TestCase):
    def test_external_origin_validation(self):
        with patch.dict('os.environ', {'PUBLIC_BASE_URL':'https://care.example.com/'}):
            self.assertEqual(public_base(),'https://care.example.com')
        for value in ['javascript:alert(1)','https://user:pass@example.com','https://example.com/path','https://example.com?secret=a']:
            with patch.dict('os.environ',{'PUBLIC_BASE_URL':value}):
                with self.assertRaises(ValueError):public_base()
    def test_lan_binding_is_distinct_from_discovery(self):
        with patch('network_config.lan_addresses',return_value=['192.168.1.8']), patch.dict('os.environ',{'PUBLIC_BASE_URL':''}):
            local=sharing_config('127.0.0.1',8765)
            self.assertFalse(local['lan_enabled'])
            self.assertEqual(local['lan_urls'],['http://192.168.1.8:8765'])
            self.assertTrue(sharing_config('0.0.0.0',8765)['lan_enabled'])
