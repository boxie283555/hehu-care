#!/usr/bin/env python3
"""One-time, transactional SQLite -> PostgreSQL import. Source remains untouched."""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from database import connect, initialize_schema, reset_sequences
TABLES=('users','children','measurements','questionnaires','assessments','plans','tasks','risks','messages','audit')

def migrate(source, apply=False, backup_dir=None):
    source=Path(source).resolve()
    if not source.is_file():raise ValueError('SQLite源文件不存在')
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
        src.row_factory=sqlite3.Row
        src.execute('BEGIN')
        if src.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('源数据库完整性检查失败')
        if src.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('源数据库存在外键错误')
        counts={t:src.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in TABLES}
        if not apply:return counts
        # A consistent backup includes data still present in SQLite's WAL.
        dest=Path(backup_dir or source.parent/'backups');dest.mkdir(parents=True,exist_ok=True)
        backup=dest/('pre-postgresql-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
        with sqlite3.connect(str(backup)) as target:src.backup(target)
        with connect() as conn:
            initialize_schema(conn)
            for table in TABLES:
                if conn.execute(psycopg.sql.SQL('SELECT count(*) FROM {}').format(psycopg.sql.Identifier(table))).fetchone()['count']:
                    raise ValueError('目标库不是空库，已停止迁移：'+table)
            for table in TABLES:
                cursor=conn.execute(psycopg.sql.SQL('SELECT * FROM {} LIMIT 0').format(psycopg.sql.Identifier(table)))
                target_columns=[col.name for col in cursor.description]
                source_columns=[row['name'] for row in src.execute('PRAGMA table_info('+table+')')]
                if set(source_columns)!=set(target_columns):raise ValueError('源表结构不兼容：'+table)
                query=psycopg.sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(psycopg.sql.Identifier(table),psycopg.sql.SQL(',').join(map(psycopg.sql.Identifier,source_columns)),psycopg.sql.SQL(',').join(psycopg.sql.Placeholder() for _ in source_columns))
                source_cursor=src.execute('SELECT * FROM '+table)
                while True:
                    batch=source_cursor.fetchmany(500)
                    if not batch:break
                    with conn.cursor() as insert:insert.executemany(query,[tuple(row) for row in batch])
                actual=conn.execute(psycopg.sql.SQL('SELECT count(*) FROM {}').format(psycopg.sql.Identifier(table))).fetchone()['count']
                if actual!=counts[table]:raise ValueError('迁移行数不匹配：'+table)
            reset_sequences(conn)
        return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--apply',action='store_true',help='导入空PostgreSQL库；默认只检查源数据')
    args=parser.parse_args()
    try:
        counts=migrate(args.source,args.apply)
        print(('迁移完成' if args.apply else '只读检查完成')+'：'+str(counts))
        if args.apply:print('原SQLite文件和迁移前备份均已保留。旧登录会话及验证码不迁移，请重新登录。')
    except Exception as exc:
        print('迁移未完成：'+type(exc).__name__+'；请检查源文件、目标空库及表结构。',file=sys.stderr)
        sys.exit(1)
