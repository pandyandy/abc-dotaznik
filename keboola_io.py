#!/usr/bin/env python3
"""
keboola_io.py — CLI bridge for the kbcstorage Python client.

Usage:
  python3 keboola_io.py export <table_id> [--where <column> <val> [<val> ...]]
  python3 keboola_io.py import <table_id>   → reads JSON array from stdin, full-replaces table
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
from kbcstorage.client import Client

# Load .env next to this script (cwd-independent; matches Node dotenv from project root)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / '.env')
except ImportError:
    pass

# Keboola Data Apps secrets are often KBC_URL / KBC_TOKEN; local .env may use KEBOOLA_* names.
KEBOOLA_URL = (os.environ.get('KEBOOLA_URL') or os.environ.get('KBC_URL') or '').rstrip('/')
STORAGE_TOKEN = os.environ.get('STORAGE_API_TOKEN') or os.environ.get('KBC_TOKEN') or ''

if not KEBOOLA_URL or not STORAGE_TOKEN:
    print(
        'Set KEBOOLA_URL and STORAGE_API_TOKEN '
        '(or KBC_URL and KBC_TOKEN for Data Apps)',
        file=sys.stderr,
    )
    sys.exit(1)

if len(sys.argv) < 3:
    print(
        'Usage: keboola_io.py export <table_id> [--where COL v1 v2 ...] | import <table_id>',
        file=sys.stderr,
    )
    sys.exit(1)

op = sys.argv[1]
table_id = sys.argv[2]

where_column = None
where_values = None
if op == 'export' and len(sys.argv) > 3:
    if sys.argv[3] == '--where' and len(sys.argv) >= 6:
        where_column = sys.argv[4]
        where_values = sys.argv[5:]
    else:
        print('Invalid export arguments (expected --where COL val [val ...])', file=sys.stderr)
        sys.exit(1)

client = Client(KEBOOLA_URL, STORAGE_TOKEN)


def export_table(tid, wcol=None, wvals=None):
    with tempfile.TemporaryDirectory() as tmpdir:
        client.tables.export_to_file(
            tid,
            tmpdir,
            where_column=wcol,
            where_values=wvals,
        )
        table_name = tid.split('.')[-1]
        file_path = os.path.join(tmpdir, table_name)
        df = pd.read_csv(file_path)
    # Normalise column names to uppercase to match Node side expectations
    df.columns = [c.upper() for c in df.columns]
    print(df.to_json(orient='records', force_ascii=False))


def import_table(tid, incremental=False):
    data = json.load(sys.stdin)
    if not data:
        return
    df = pd.DataFrame(data)
    # Numbers were stored as strings with comma decimal in the original app;
    # keep them as-is so the Keboola table content is unchanged.
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, encoding='utf-8'
    ) as f:
        df.to_csv(f, index=False)
        tmp_path = f.name
    try:
        client.tables.load(
            table_id=tid,
            file_path=tmp_path,
            is_incremental=incremental,
        )
    finally:
        os.unlink(tmp_path)


if op == 'export':
    export_table(table_id, where_column, where_values)
elif op == 'import':
    incremental = '--incremental' in sys.argv
    import_table(table_id, incremental)
else:
    print(f'Unknown operation: {op}', file=sys.stderr)
    sys.exit(1)
