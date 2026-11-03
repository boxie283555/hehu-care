#!/usr/bin/env python3
"""Start the local service in the background; double-click 启动禾护.command."""
import os, sys, subprocess, time, json, urllib.request, webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8765'
DATA=ROOT/'data'
def ready():
    try:
        with urllib.request.urlopen(URL+'/api/config',timeout=1) as r:
            return json.load(r).get('app')=='hehu-care'
    except Exception:return False
if not ready():
    DATA.mkdir(exist_ok=True)
    with open(DATA/'server.log','ab') as log:
        p=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=str(ROOT),stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'HOST':'127.0.0.1','PORT':'8765'})
    (DATA/'server.pid').write_text(str(p.pid))
    for _ in range(40):
        if ready():break
        if p.poll() is not None:raise SystemExit('服务未启动，请查看 data/server.log（可能端口已被占用）。')
        time.sleep(.15)
    else:raise SystemExit('启动超时，请查看 data/server.log。')
print('禾护已运行：'+URL)
if '--no-browser' not in sys.argv:webbrowser.open(URL)
