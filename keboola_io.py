#!/usr/bin/env python3
"""
keboola_io.py — CLI bridge for the kbcstorage Python client.

Usage:
  python3 keboola_io.py export <table_id>   → JSON array on stdout
  python3 keboola_io.py import <table_id>   → reads JSON array from stdin, full-replaces table
"""

import json
import os
import sys
import tempfile

import pandas as pd
from kbcstorage.client import Client

KEBOOLA_URL = os.environ.get('KEBOOLA_URL', '')
STORAGE_TOKEN = os.environ.get('STORAGE_API_TOKEN', '')

if not KEBOOLA_URL or not STORAGE_TOKEN:
    print('KEBOOLA_URL and STORAGE_API_TOKEN must be set', file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 3:
    print('Usage: keboola_io.py export|import <table_id>', file=sys.stderr)
    sys.exit(1)

op = sys.argv[1]
table_id = sys.argv[2]

client = Client(KEBOOLA_URL.rstrip('/'), STORAGE_TOKEN)


def export_table(tid):
    with tempfile.TemporaryDirectory() as tmpdir:
        client.tables.export_to_file(tid, tmpdir)
        table_name = tid.split('.')[-1]
        file_path = os.path.join(tmpdir, table_name)
        df = pd.read_csv(file_path)
    # Normalise column names to uppercase to match Node side expectations
    df.columns = [c.upper() for c in df.columns]
    print(df.to_json(orient='records', force_ascii=False))


def import_table(tid):
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
            is_incremental=False,
        )
    finally:
        os.unlink(tmp_path)


if op == 'export':
    export_table(table_id)
elif op == 'import':
    import_table(table_id)
else:
    print(f'Unknown operation: {op}', file=sys.stderr)
    sys.exit(1)
