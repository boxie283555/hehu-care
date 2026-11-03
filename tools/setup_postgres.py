"""Provision a private, project-owned PostgreSQL cluster on Windows.

An explicit DATABASE_URL always wins. No system service or existing cluster is modified.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from dotenv import dotenv_values
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
VERSION = '17.10-1'
ARCHIVE_URL = f'https://get.enterprisedb.com/postgresql/postgresql-{VERSION}-windows-x64-binaries.zip'
ARCHIVE_SHA256 = 'f9aafca58e7026a1ef2caeee711acf761671e57904d430adc85f468374f5a821'


def run(args, **kwargs):
    # Do not echo commands or connection parameters: they can contain secrets.
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def protect(path):
    if os.name == 'nt':
        # Apply to our own directory only, before any credentials are written.
        who = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True, encoding='utf-8', errors='replace')
        import csv
        sid = next(csv.reader([who.strip()]))[1]
        run(['icacls', path, '/inheritance:r', '/grant:r', f'*{sid}:' + ('(OI)(CI)F' if path.is_dir() else 'F'), '*S-1-5-18:' + ('(OI)(CI)F' if path.is_dir() else 'F')], stdout=subprocess.DEVNULL)
    else:
        path.chmod(0o700)


def write_private(path, text):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.hehu-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            if os.name == 'nt': protect(Path(name))
            f.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def lock(directory):
    with (directory/'setup.lock').open('a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another database setup is running. Retry after it finishes.') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def install_runtime(directory):
    if os.name == 'nt':
        run(['powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ROOT/'tools/install-vcredist.ps1'])
    target = directory/'runtime'
    if (target/'pgsql/bin/pg_ctl.exe').is_file():
        return target/'pgsql/bin'
    arch = os.environ.get('PROCESSOR_ARCHITEW6432') or os.environ.get('PROCESSOR_ARCHITECTURE', '')
    if arch.upper() != 'AMD64':
        raise RuntimeError('Automatic PostgreSQL installation requires x64 Windows. Configure DATABASE_URL for another architecture.')
    print(f'Downloading PostgreSQL {VERSION} from EnterpriseDB (about 320 MB)…', flush=True)
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        temp = Path(temp); archive = temp/'postgres.zip'
        with urllib.request.urlopen(ARCHIVE_URL, timeout=120) as src, archive.open('wb') as dst:
            shutil.copyfileobj(src, dst)
        h = hashlib.sha256()
        with archive.open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
        digest = h.hexdigest()
        if digest != ARCHIVE_SHA256:
            raise RuntimeError('PostgreSQL download checksum mismatch; nothing was installed. Retry or update the installer.')
        unpack = temp/'unpack'; unpack.mkdir()
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                dest = (unpack/member.filename).resolve()
                if not str(dest).startswith(str(unpack.resolve()) + os.sep):
                    raise RuntimeError('Invalid PostgreSQL archive path.')
            z.extractall(unpack)
        if not (unpack/'pgsql/bin/initdb.exe').is_file():
            raise RuntimeError('Invalid PostgreSQL binary archive.')
        unpack.rename(target)
    return target/'pgsql/bin'


def free_port():
    for port in range(55432, 55452):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1', port))
            except OSError: continue
            return port
    raise RuntimeError('No free local PostgreSQL port in 55432–55451.')


def provision(directory, binaries):
    statefile = directory/'state.json'
    if statefile.exists():
        state = json.loads(statefile.read_text(encoding='utf-8'))
    else:
        state = {'port': free_port(), 'admin_password': secrets.token_hex(32), 'app_password': secrets.token_hex(32)}
        write_private(statefile, json.dumps(state))
    cluster = directory/'cluster'
    suffix = '.exe' if os.name == 'nt' else ''
    def exe(name): return binaries/(name+suffix)
    if not (cluster/'PG_VERSION').exists():
        if cluster.exists() and any(cluster.iterdir()):
            raise RuntimeError('Incomplete database initialization. Preserve the cluster directory and inspect the setup error before retrying.')
        password_file = directory/'init-password'
        try:
            write_private(password_file, state['admin_password'])
            run([exe('initdb'), '-D', cluster, '-U', 'hehu_admin', '--pwfile', password_file,
                 '--auth-host=scram-sha-256', '--auth-local=scram-sha-256', '--encoding=UTF8', '--locale=C'])
        finally:
            password_file.unlink(missing_ok=True)
    # A separate owned config survives a retry interrupted after initdb.
    write_private(cluster/'postgresql.auto.conf',
                  "listen_addresses = '127.0.0.1'\nport = %d\npassword_encryption = 'scram-sha-256'\n" % state['port'])
    status = subprocess.run([str(exe('pg_ctl')), '-D', str(cluster), 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode != 0:
        run([exe('pg_ctl'), '-D', cluster, '-l', directory/'postgres.log', '-w', '-t', '60', 'start'])
    with psycopg.connect(host='127.0.0.1', port=state['port'], user='hehu_admin', password=state['admin_password'], dbname='postgres', autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='hehu'").fetchone():
            conn.execute(sql.SQL('CREATE ROLE hehu LOGIN PASSWORD {}').format(sql.Literal(state['app_password'])))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='hehu'").fetchone():
            conn.execute('CREATE DATABASE hehu OWNER hehu')
    url = f"postgresql://hehu:{state['app_password']}@127.0.0.1:{state['port']}/hehu"
    with psycopg.connect(url) as conn:
        conn.execute('SELECT 1')
    return url


def setup(root=ROOT, binaries=None):
    envfile = root/'.env'
    configured = os.environ.get('DATABASE_URL') or dotenv_values(envfile).get('DATABASE_URL')
    directory = root/'data/postgres'
    statefile = directory/'state.json'
    if configured:
        # Only start the managed cluster when its exact persisted URL is in use.
        state = json.loads(statefile.read_text(encoding='utf-8')) if statefile.exists() else {}
        owned = f"postgresql://hehu:{state.get('app_password')}@127.0.0.1:{state.get('port')}/hehu"
        if configured != owned:
            print('Using configured DATABASE_URL; automatic database installation skipped.', flush=True)
            return
    elif os.name != 'nt' and binaries is None:
        raise RuntimeError('Configure DATABASE_URL first. Automatic local PostgreSQL deployment is available on Windows x64.')
    directory.mkdir(parents=True, exist_ok=True); protect(directory)
    with lock(directory):
        binaries = binaries or install_runtime(directory)
        url = provision(directory, binaries)
        if not configured:
            previous = envfile.read_text(encoding='utf-8') if envfile.exists() else ''
            # Empty DATABASE_URL lines are allowed, but preserve all other settings.
            lines = [line for line in previous.splitlines() if not line.strip().startswith(('DATABASE_URL=', 'export DATABASE_URL='))]
            lines.append('DATABASE_URL='+url)
            if 'SEED_DEMO' not in dotenv_values(envfile): lines.append('SEED_DEMO=0')
            write_private(envfile, '\n'.join(lines)+'\n')
        print('Local PostgreSQL is ready. Credentials saved in .env; database listens on 127.0.0.1 only.', flush=True)

if __name__ == '__main__':
    try:
        setup()
    except Exception as error:
        # Driver errors can include DSNs; avoid printing credentials.
        if isinstance(error, RuntimeError): print(str(error), file=sys.stderr)
        print(f'Database setup failed ({type(error).__name__}). Check network, disk space, port conflicts and data/postgres/postgres.log. Existing data was preserved.', file=sys.stderr)
        sys.exit(1)
