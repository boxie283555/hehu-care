#!/usr/bin/env python3
"""Cross-platform background launcher. Windows users can also run start-windows.cmd."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'


def ready(url):
    # Local health checks must not pass through a configured HTTP proxy.
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + '/api/config', timeout=1) as response:
            return json.load(response).get('app') == 'hehu-care'
    except Exception:
        return False


def process_options(windows):
    if windows:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB.
        # The last flag allows the child to outlive a debugger job when permitted.
        return {'creationflags': 0x00000008 | 0x00000200 | 0x01000000}
    return {'start_new_session': True}


def start_service(host, port):
    DATA.mkdir(exist_ok=True)
    # debugpy otherwise injects debugging into Popen children, keeping the server
    # coupled to the launcher debug session even when its console is detached.
    debugger = sys.modules.get('debugpy')
    if debugger is not None:
        debugger.configure(subProcess=False)
    env = {**os.environ, 'HOST': host, 'PORT': str(port), 'PYTHONUTF8': '1'}
    for key in list(env):
        if key.startswith(('DEBUGPY_', 'PYDEVD_')):
            env.pop(key)
    options = process_options(sys.platform == 'win32')
    with open(DATA / 'server.log', 'ab') as log:
        args = dict(cwd=str(ROOT), stdout=log, stderr=log,
                    stdin=subprocess.DEVNULL, env=env, close_fds=True)
        command = [sys.executable, str(ROOT / 'server.py')]
        try:
            child = subprocess.Popen(command, **args, **options)
        except OSError as exc:
            if sys.platform != 'win32' or getattr(exc, 'winerror', None) != 5:
                raise
            # Some Windows job policies disallow breakaway. The foreground CMD
            # entry point remains available independently of VS Code.
            options['creationflags'] &= ~0x01000000
            child = subprocess.Popen(command, **args, **options)
            print('Windows限制了进程脱离；如停止调试后服务退出，请使用 start-windows.cmd。')
    return child


def main():
    parser = argparse.ArgumentParser(description='启动禾护本地服务')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8765')))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须在1到65535之间')
    visit_host = '127.0.0.1' if args.host == '0.0.0.0' else args.host
    url = 'http://%s:%s' % (visit_host, args.port)
    if not ready(url):
        child = start_service(args.host, args.port)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('服务启动失败，请查看 %s（检查端口占用及文件权限）。' % (DATA / 'server.log'))
            if ready(url):
                (DATA / 'server.pid').write_text(str(child.pid))
                break
            time.sleep(.15)
        else:
            child.terminate()
            raise RuntimeError('启动超时，请查看 %s。' % (DATA / 'server.log'))
    print('禾护已运行：' + url)
    if args.host == '0.0.0.0':
        print('局域网访问请使用本机实际IP，端口：' + str(args.port))
    if not args.no_browser:
        webbrowser.open(url)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print('启动失败：' + str(exc), file=sys.stderr)
        sys.exit(1)
