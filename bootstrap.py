#!/usr/bin/env python3
"""Prepare project dependencies in an isolated venv, then start Hehu."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent

def main():
    runtime=ROOT/'data/venv'
    python=runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        subprocess.run([sys.executable,'-m','venv',str(runtime)],check=True)
    requirement=ROOT/'requirements.txt'
    digest=hashlib.sha256(requirement.read_bytes()).hexdigest()
    marker=runtime/'hehu-requirements.sha256'
    ready=subprocess.run([str(python),'-c','import psycopg, psycopg_pool, dotenv'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not ready or not marker.exists() or marker.read_text()!=digest:
        print('正在安装 PostgreSQL 驱动和项目依赖…',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(requirement)],check=True)
        marker.write_text(digest)
    args=sys.argv[1:]
    if '--foreground' in args:
        args.remove('--foreground');target='server.py'
    else:target='launcher.py'
    return subprocess.call([str(python),str(ROOT/target),*args],cwd=str(ROOT))

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,subprocess.CalledProcessError):
        print('启动失败：请检查Python环境、网络及项目目录写权限。',file=sys.stderr);sys.exit(1)
