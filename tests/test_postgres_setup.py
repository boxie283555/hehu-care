import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from dotenv import dotenv_values
import psycopg
from tools import setup_postgres as setup

class SetupTests(unittest.TestCase):
    def test_external_database_is_never_installed_or_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'DATABASE_URL': 'postgresql://external/db'}):
            root=Path(tmp); (root/'.env').write_text('SEED_DEMO=0\n')
            with patch.object(setup,'install_runtime') as install:
                setup.setup(root)
                install.assert_not_called()
            self.assertFalse((root/'data').exists())
            self.assertEqual((root/'.env').read_text(),'SEED_DEMO=0\n')

    def test_download_hash_failure_never_extracts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'PROCESSOR_ARCHITEW6432':'AMD64'}):
            with patch.object(setup,'run'), patch.object(setup.urllib.request,'urlopen',return_value=io.BytesIO(b'corrupt download')):
                with self.assertRaisesRegex(RuntimeError,'checksum mismatch'):
                    setup.install_runtime(Path(tmp))
            self.assertFalse((Path(tmp)/'runtime').exists())

    def test_verified_archive_installs_and_is_reused(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('pgsql/bin/initdb.exe',b'test')
            z.writestr('pgsql/bin/pg_ctl.exe',b'test')
        raw=data.getvalue()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'PROCESSOR_ARCHITEW6432':'AMD64'}):
            with patch.object(setup,'run'), patch.object(setup,'ARCHIVE_SHA256',hashlib.sha256(raw).hexdigest()), patch.object(setup.urllib.request,'urlopen',return_value=io.BytesIO(raw)) as fetch:
                first=setup.install_runtime(Path(tmp)); second=setup.install_runtime(Path(tmp))
                self.assertEqual(first,second); self.assertTrue((first/'initdb.exe').exists()); self.assertEqual(fetch.call_count,1)

    @unittest.skipUnless(os.environ.get('HEHU_TEST_PG_BIN'),'Set HEHU_TEST_PG_BIN for real isolated cluster lifecycle test')
    def test_real_cluster_init_restart_preserves_data_and_settings(self):
        binaries=Path(os.environ['HEHU_TEST_PG_BIN'])
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            os.environ.pop('DATABASE_URL',None)
            root=Path(tmp); (root/'.env').write_text('PORT=8877\nSEED_DEMO=0\n')
            cluster=root/'data/postgres/cluster'
            pgctl=binaries/('pg_ctl.exe' if os.name=='nt' else 'pg_ctl')
            try:
                setup.setup(root,binaries)
                original=(root/'.env').read_bytes()
                env=dotenv_values(root/'.env'); self.assertEqual(env['PORT'],'8877')
                self.assertEqual(env['SEED_DEMO'],'0')
                with psycopg.connect(env['DATABASE_URL']) as c:
                    c.execute('CREATE TABLE retained (value text)')
                    c.execute("INSERT INTO retained VALUES ('保留数据')")
                    self.assertFalse(c.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user").fetchone()[0])
                    self.assertEqual(c.execute('SHOW listen_addresses').fetchone()[0],'127.0.0.1')
                subprocess.run([str(pgctl),'-D',str(cluster),'-m','fast','-w','stop'],check=True,stdout=subprocess.DEVNULL)
                setup.setup(root,binaries)
                setup.setup(root,binaries)
                self.assertEqual(original,(root/'.env').read_bytes())
                with psycopg.connect(env['DATABASE_URL']) as c:
                    self.assertEqual(c.execute('SELECT value FROM retained').fetchone()[0],'保留数据')
            finally:
                if (cluster/'PG_VERSION').exists():
                    subprocess.run([str(pgctl),'-D',str(cluster),'-m','fast','-w','stop'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
