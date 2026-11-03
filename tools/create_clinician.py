#!/usr/bin/env python3
"""Create a clinician interactively without putting passwords in command history."""
import argparse
import getpass
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import connect,initialize_schema
from server import password_hash
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    password=getpass.getpass('Password (minimum 12 characters): ')
    if len(password)<12 or password!=getpass.getpass('Confirm password: '):raise SystemExit('Password too short or confirmation did not match.')
    salt=secrets.token_hex(16)
    with connect() as c:
        initialize_schema(c)
        if c.execute('SELECT id FROM users WHERE phone=%s',(args.username,)).fetchone():raise SystemExit('Username already exists; no changes made.')
        c.execute("INSERT INTO users(phone,name,role,salt,password) VALUES(%s,%s,'clinician',%s,%s)",(args.username,args.name,salt,password_hash(password,salt)))
    print('Clinician account created.')
