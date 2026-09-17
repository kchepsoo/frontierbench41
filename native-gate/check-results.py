#!/usr/bin/env python3
"""Native execution smoke gate, not a performance or difficulty benchmark."""
from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

LOGS = Path('/work/logs')
QUERIES = {
    'aggregate': '''SELECT o.category, count(*), sum(l.quantity)
        FROM orders o JOIN lineitems l ON o.order_id=l.order_id
        GROUP BY o.category''',
    'duplicates': '''SELECT o.category,l.quantity FROM orders o
        JOIN lineitems l ON o.order_id=l.order_id WHERE o.order_id<100''',
    'outer_join': '''SELECT o.category,count(l.order_id) FROM orders o
        LEFT JOIN lineitems l ON o.order_id=l.order_id
        GROUP BY o.category''',
}


def psql(sql):
    started = time.monotonic()
    result = subprocess.run(
        ['psql', '-X', '-q', '-A', '-t', '-F', '\t',
         '-v', 'ON_ERROR_STOP=1'], input=sql, text=True, capture_output=True,
        check=True)
    return result.stdout, result.stderr, time.monotonic()-started


def main():
    if os.getuid() == 0:
        raise RuntimeError('Database check must run as non-root')
    orders = [(i, i % 7) for i in range(2000)]
    lines = [(i % 1900, i % 5 + 1) for i in range(10000)]
    for name, rows in [('orders', orders), ('lineitems', lines)]:
        with Path('/work', name+'.csv').open('w', newline='') as f:
            csv.writer(f).writerows(rows)
    psql('''CREATE TABLE orders(order_id integer,category integer)
        DISTRIBUTED BY (order_id);
        CREATE TABLE lineitems(order_id integer,quantity integer)
        DISTRIBUTED BY (order_id);
        \\copy orders FROM '/work/orders.csv' WITH (FORMAT csv)
        \\copy lineitems FROM '/work/lineitems.csv' WITH (FORMAT csv)
        ANALYZE orders;
        ANALYZE lineitems;
    ''')
    oracle = sqlite3.connect(':memory:')
    oracle.execute('CREATE TABLE orders(order_id integer,category integer)')
    oracle.execute('CREATE TABLE lineitems(order_id integer,quantity integer)')
    oracle.executemany('INSERT INTO orders VALUES (?,?)', orders)
    oracle.executemany('INSERT INTO lineitems VALUES (?,?)', lines)
    records = []
    for name, sql in QUERIES.items():
        actual, notices, wall = psql('SET optimizer=on;\n'+sql+';')
        actual_bag = Counter(tuple(line.split('\t')) for line in actual.splitlines())
        expected_bag = Counter(tuple(str(x) for x in row)
                               for row in oracle.execute(sql))
        if actual_bag != expected_bag:
            raise RuntimeError('Independent multiset comparison failed: '+name)
        if name == 'duplicates' and max(expected_bag.values()) <= 1:
            raise RuntimeError('Smoke data failed to exercise duplicates')
        plan, plan_notices, explain_wall = psql(
            'SET optimizer=on; EXPLAIN (ANALYZE, TIMING ON) '+sql+';')
        (LOGS/(name+'-explain.txt')).write_text(plan)
        (LOGS/(name+'-notices.txt')).write_text(notices+plan_notices)
        (LOGS/(name+'-results.tsv')).write_text(actual)
        if not re.search(r'Optimizer:\s*GPORCA', plan):
            raise RuntimeError('GPORCA plan not proven; possible fallback: '+name)
        timings = {}
        for kind in ('Planning', 'Execution'):
            match = re.search(kind+r' [Tt]ime:\s*([0-9.]+)\s*ms', plan)
            if match is None:
                raise RuntimeError('Native '+kind+' timing absent: '+name)
            timings[kind.lower()+'_ms'] = float(match.group(1))
        records.append({'query': name, 'multiset_correct': True,
                        'rows': sum(actual_bag.values()),
                        'distinct_rows': len(actual_bag),
                        'client_wall_seconds': wall,
                        'explain_client_wall_seconds': explain_wall, **timings})
    (LOGS/'smoke-result.json').write_text(json.dumps({
        'gate': 'NATIVE_SMOKE_PASS', 'database_uid': os.getuid(),
        'scope': 'Generated smoke data only; no TPC-H/JOB/TPC-DS inference.',
        'recovery_scores': None,
        'timing_scope': 'Instrumented EXPLAIN timing, unsuitable as final score.',
        'queries': records}, indent=2)+'\n')
    print('NATIVE_SMOKE_PASS: three GPORCA plans, native execution, exact bags')


if __name__ == '__main__':
    main()
