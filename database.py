"""PostgreSQL connections, bounded pooling and schema initialization."""
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env',override=False)
_pool=None
_lock=threading.Lock()
ID_TABLES=('users','children','measurements','questionnaires','assessments','plans','tasks','risks','messages','audit')

def schema_name():
    schema=os.environ.get('HEHU_DB_SCHEMA','public')
    if not re.fullmatch('[a-z][a-z0-9_]{0,62}',schema):raise RuntimeError('HEHU_DB_SCHEMA 必须是小写字母、数字或下划线组成的有效schema名')
    return schema

def pool():
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                dsn=os.environ.get('DATABASE_URL')
                if not dsn:raise RuntimeError('请在 .env 中设置 PostgreSQL DATABASE_URL；不会自动回退到SQLite。')
                maximum=int(os.environ.get('DB_POOL_MAX','10'))
                if not 1<=maximum<=100:raise RuntimeError('DB_POOL_MAX 必须在1到100之间')
                candidate=ConnectionPool(dsn,min_size=1,max_size=maximum,timeout=10,max_waiting=100,
                    kwargs={'row_factory':dict_row,'connect_timeout':5,'options':'-c search_path='+schema_name()+' -c statement_timeout=15000 -c lock_timeout=10000'},open=False)
                try:
                    candidate.open(wait=True,timeout=10)
                except Exception:
                    candidate.close()
                    raise RuntimeError('PostgreSQL连接失败，请检查数据库服务、DATABASE_URL和账号权限。') from None
                _pool=candidate
    return _pool

@contextmanager
def connect():
    with pool().connection() as conn:
        yield conn

def close_pool():
    global _pool
    if _pool is not None:_pool.close();_pool=None

def initialize_schema(conn):
    # Serialize schema initialization and demo seeding across server instances.
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('hehu-schema:'+schema_name(),))
    conn.execute(psycopg.sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(psycopg.sql.Identifier(schema_name())))
    for statement in (ROOT/'sql/001_initial.sql').read_text(encoding='utf-8').split(';'):
        if statement.strip():conn.execute(statement)

def reset_sequences(conn):
    for table in ID_TABLES:
        conn.execute(psycopg.sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'),COALESCE(MAX(id),1),MAX(id) IS NOT NULL) FROM {}").format(psycopg.sql.Identifier(table)),(schema_name()+'.'+table,))
