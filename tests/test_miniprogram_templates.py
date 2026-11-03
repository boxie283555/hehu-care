import json
import re
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]/'miniprogram'

class MiniProgramTemplateTests(unittest.TestCase):
    def test_declared_pages_have_valid_bound_templates(self):
        pages=json.loads((ROOT/'app.json').read_text(encoding='utf-8'))['pages']
        for page in pages:
            with self.subTest(page=page):
                for ext in ('js','json','wxml'):
                    self.assertTrue((ROOT/(page+'.'+ext)).is_file())
                json.loads((ROOT/(page+'.json')).read_text(encoding='utf-8'))
                source=(ROOT/(page+'.wxml')).read_text(encoding='utf-8')
                for attribute,expression in re.findall(r'wx:(if|elif|for)="([^"]*)"',source):
                    self.assertTrue(expression.startswith('{{') and expression.endswith('}}'),attribute+' must use a dynamic binding')
                normalized=re.sub(r'wx:else(?=[\s>])','wx:else=""',source)
                tree=ET.fromstring('<root xmlns:wx="urn:wechat">'+normalized+'</root>')
                for element in tree.iter():
                    self.assertIn(element.tag,{'root','view','text','button','input','textarea','picker','checkbox-group','checkbox','label','block'})
