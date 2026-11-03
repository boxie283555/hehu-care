"""Create/drop isolated PostgreSQL schemas for automated tests, never app data."""
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
import psycopg
from psycopg import sql
load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
def create():
    name='hehu_test_'+uuid.uuid4().hex
    with psycopg.connect(os.environ['DATABASE_URL']) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    return name

def drop(name):
    if not name.startswith('hehu_test_') or len(name)!=42:raise ValueError('Only test schemas may be removed')
    with psycopg.connect(os.environ['DATABASE_URL']) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))

if __name__=='__main__':
    if sys.argv[1]=='create':print(create())
    elif sys.argv[1]=='drop':drop(sys.argv[2])
