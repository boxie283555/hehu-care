import importlib.util
import subprocess
import sys
import tempfile
import socket
import os
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launcher', ROOT / 'launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def test_windows_detachment_and_debugger_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            debugger=Mock()
            with patch.object(launcher,'DATA',Path(tmp)), patch.object(launcher.sys,'platform','win32'), patch.dict(sys.modules,{'debugpy':debugger}), patch.object(launcher.subprocess,'Popen') as spawn:
                launcher.start_service('0.0.0.0',8877)
                debugger.configure.assert_called_once_with(subProcess=False)
                opts=spawn.call_args.kwargs
                self.assertEqual(opts['creationflags'],0x01000208)
                self.assertNotIn('start_new_session',opts)
                self.assertEqual(opts['env']['HOST'],'0.0.0.0')
                self.assertEqual(opts['env']['PORT'],'8877')
    def test_windows_breakaway_denied_fallback(self):
        error=OSError('Access denied');error.winerror=5
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(launcher,'DATA',Path(tmp)), patch.object(launcher.sys,'platform','win32'), patch.object(launcher.subprocess,'Popen',side_effect=[error,Mock()]) as spawn:
                launcher.start_service('127.0.0.1',8877)
                self.assertEqual(spawn.call_args.kwargs['creationflags'],0x208)
    @unittest.skipIf(sys.platform=='win32','POSIX lifecycle check; Windows flags covered separately')
    def test_server_survives_launcher_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
            env={**os.environ,'CARE_DB':str(Path(tmp)/'test.db')}
            # Redirect launcher runtime files away from the real application's PID.
            code='import launcher; from pathlib import Path; launcher.DATA=Path(%r); launcher.main()' % tmp
            result=subprocess.run([sys.executable,'-c',code,'--port',str(port),'--host','127.0.0.1','--no-browser'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=25)
            pidfile=Path(tmp)/'server.pid'
            try:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue(launcher.ready('http://127.0.0.1:'+str(port)))
            finally:
                if pidfile.exists():os.kill(int(pidfile.read_text()),15)
