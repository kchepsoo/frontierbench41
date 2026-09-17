#!/usr/bin/env python3
"""Frozen native 2x2 pilot. Estimated optimizer costs never enter scoring."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import math
import numbers
import os
from pathlib import Path
import random
import re
import time
import traceback
import urllib.request
import duckdb
import psycopg2

LOG = Path('/work/logs')
CELLS = {'W': (0, 0), 'E': (1, 0), 'O': (0, 1), 'EO': (1, 1)}
TABLES = ['region', 'nation', 'supplier', 'customer', 'part', 'partsupp', 'orders', 'lineitem']
ORIGINAL_PROTOCOL = 'b5fc8107e966211a08afae67447c558ebabea2a551dab53759ebce93ffca5387'


def encoded(x):
    return json.dumps(x, sort_keys=True, default=str, separators=(',', ':'))


def save(name, value):
    path = LOG / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + '\n')


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def event(stage, **fields):
    entry = {'utc': datetime.now(timezone.utc).isoformat(), 'stage': stage, **fields}
    with (LOG/'events.jsonl').open('a') as f:
        f.write(encoded(entry)+'\n')
    print(encoded(entry), flush=True)


def connect(e=1, o=1, trace=False, mode='exhaustive'):
    c = psycopg2.connect('')
    c.autocommit = True
    with c.cursor() as cur:
        settings = {
            'optimizer': 'on', 'optimizer_join_order': mode,
            'optimizer_audit_e': str(e), 'optimizer_audit_o': str(o),
            'optimizer_audit_trace': 'on' if trace else 'off',
            'optimizer_metadata_caching': 'off', 'plan_cache_mode': 'force_generic_plan',
            'statement_timeout': '0', 'optimizer_nestloop_factor': '1024',
            'optimizer_sort_factor': '1', 'optimizer_spilling_mem_threshold': '0',
            'gp_autostats_mode': 'none', 'gp_autostats_mode_in_functions': 'none',
        }
        for key, value in settings.items():
            cur.execute('SET '+key+' = %s', (value,))
        cur.execute('SET search_path = tpch, public')
    return c


def one(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def native_plan(cur, sql, analyze=False):
    prefix = 'EXPLAIN (FORMAT JSON' + (', ANALYZE, TIMING OFF' if analyze else '') + ') '
    result = one(cur, prefix + sql)
    if isinstance(result, str):
        result = json.loads(result)
    plan = result[0]
    if 'GPORCA' not in str(plan.get('Settings', {}).get('Optimizer', plan.get('Optimizer', ''))):
        raise RuntimeError('GPORCA attribution missing: '+encoded(plan)[:500])
    return plan


def structural_plan(plan):
    """Remove only execution observations; retain physical choices/estimates."""
    runtime = {'Workers', 'JIT', 'Slice statistics', 'Memory', 'Peak Memory Usage',
               'Hash Buckets', 'Original Hash Buckets', 'Hash Batches', 'Original Hash Batches',
               'Sort Method', 'Sort Space Used', 'Sort Space Type'}
    if isinstance(plan, dict):
        return {k: structural_plan(v) for k, v in plan.items()
                if not k.startswith(('Actual ', 'Rows Removed', 'Shared ', 'Local ', 'Temp ', 'I/O ', 'WAL '))
                and k not in runtime}
    if isinstance(plan, list):
        return [structural_plan(v) for v in plan]
    return plan


def exact_part(row):
    return tuple(('number',) if isinstance(v, (Decimal, float)) else
                 ('null',) if v is None else ('exact', str(v)) for v in row)


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (Decimal, float)) or isinstance(b, (Decimal, float)):
        if not isinstance(a, numbers.Number) or not isinstance(b, numbers.Number):
            return False
        aa, bb = Decimal(str(a)), Decimal(str(b))
        return abs(aa-bb) <= Decimal('0.000001') + Decimal('0.0000000001')*max(abs(aa), abs(bb))
    return type(a) == type(b) and a == b


def compare_bags(expected, actual):
    if len(expected) != len(actual):
        raise AssertionError(f'bag sizes differ: {len(expected)} vs {len(actual)}')
    left, right = defaultdict(list), defaultdict(list)
    for row in expected:
        left[exact_part(row)].append(row)
    for row in actual:
        right[exact_part(row)].append(row)
    if left.keys() != right.keys():
        raise AssertionError('exact result fields or NULL positions differ')
    # Maximum bipartite matching preserves multiplicity and avoids ambiguous
    # greedy tolerance matches. TPC-H result groups are small here.
    for key, rows in left.items():
        targets = right[key]
        if len(rows) != len(targets):
            raise AssertionError('result multiplicities differ')
        edges = [[j for j, target in enumerate(targets)
                  if all(close(a, b) for a, b in zip(row, target))]
                 for row in rows]
        matched = {}
        def augment(i, seen):
            for j in edges[i]:
                if j in seen:
                    continue
                seen.add(j)
                if j not in matched or augment(matched[j], seen):
                    matched[j] = i
                    return True
            return False
        for i in range(len(rows)):
            if not augment(i, set()):
                raise AssertionError('numeric bag comparison failed: '+str(rows[i]))
    return {'rows': len(actual), 'distinct_rows': len(Counter(map(tuple, actual))),
            'expected_sha256': digest(expected), 'actual_sha256': digest(actual),
            'complete_multiset_correct': True}


def prepare_data():
    extension = Path('/work/tpch.duckdb_extension')
    url = 'https://extensions.duckdb.org/v1.4.3/linux_amd64/tpch.duckdb_extension.gz'
    req = urllib.request.Request(url, headers={'User-Agent': 'frontierbench-native-pilot/1'})
    extension.write_bytes(gzip.decompress(urllib.request.urlopen(req, timeout=120).read()))
    oracle = duckdb.connect('/work/oracle.duckdb')
    oracle.execute("LOAD '"+str(extension)+"'")  # DuckDB checks the official signature.
    oracle.execute('SET threads=2')
    oracle.execute('CALL dbgen(sf=0.1)')
    queries = {int(n): q.strip().rstrip(';') for n, q in oracle.execute('FROM tpch_queries()').fetchall()}
    assert set(queries) == set(range(1, 23))
    save('queries.json', queries)
    with connect() as db, db.cursor() as cur:
        cur.execute('CREATE SCHEMA tpch')
        manifest = []
        for table in TABLES:
            description = oracle.execute('DESCRIBE '+table).fetchall()
            columns = [(r[0], r[1]) for r in description]
            definition = ','.join(name+' '+typ for name, typ in columns)
            cur.execute('CREATE TABLE '+table+' ('+definition+') WITH (autovacuum_enabled=false) DISTRIBUTED BY ('+columns[0][0]+')')
            path = Path('/work/'+table+'.csv')
            oracle.execute("COPY "+table+" TO '"+str(path)+"' (FORMAT CSV, HEADER false, NULL '\\N')")
            with path.open() as f:
                cur.copy_expert("COPY "+table+" FROM STDIN WITH (FORMAT CSV, NULL '\\N')", f)
            cur.execute('ANALYZE '+table)
            expected = oracle.execute('SELECT count(*) FROM '+table).fetchone()[0]
            actual = one(cur, 'SELECT count(*) FROM '+table)
            assert expected == actual
            manifest.append({'table': table, 'columns': columns, 'rows': actual,
                             'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        cur.execute('SHOW ALL')
        save('settings.json', cur.fetchall())
    expected = {}
    for n, sql in queries.items():
        expected[n] = oracle.execute(sql).fetchall()
        save(f'oracle/q{n:02d}.json', expected[n])
    save('workload.json', {'sf': 0.1, 'duckdb': duckdb.__version__, 'tables': manifest,
                         'extension_url': url, 'extension_sha256': hashlib.sha256(extension.read_bytes()).hexdigest(),
                         'query_sha256': {n: hashlib.sha256(q.encode()).hexdigest() for n, q in queries.items()}})
    return queries, expected


def statistics_snapshot():
    with connect() as db, db.cursor() as cur:
        cur.execute("SELECT c.relname,c.reltuples,c.relpages,s.* FROM pg_statistic s JOIN pg_class c ON c.oid=s.starelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='tpch' ORDER BY c.relname,s.staattnum,s.stainherit")
        rows = cur.fetchall()
    return rows


def parse_trace(path):
    s = path.read_text()
    policies = re.findall(r'AUDIT_POLICY E (-?\d+) O (-?\d+) FALLBACK (\d) P_FIXED (\d)', s)
    disabled = re.findall(r'AUDIT_DISABLED_XFORMS ([0-9,]*)', s)
    costs = re.findall(r'AUDIT_COST (FULL|PARTIAL) MODEL (\d+) HOSTS (\d+) OP (\d+) INPUT (.*?) CHILDREN (.*?) OUTPUT ([^\n]+)', s)
    joins = defaultdict(set)
    for key, requests, origin, fixed in re.findall(r'AUDIT_HJ_BEGIN\nKEY\n(.*?)REQUESTS\n(.*?)ORIGIN (\d+) FIXED (\d)\nAUDIT_HJ_END', s, re.S):
        assert fixed == '1'
        key = re.sub(r'0x[0-9a-fA-F]+', 'PTR', key)
        joins[key].add(requests)
    assert policies and disabled and costs, 'missing native policy/cost diagnostics'
    assert all(len(values) == 1 for values in joins.values()), 'P requests vary within a common join identity'
    return {'policies': policies, 'disabled': disabled[-1], 'costs': costs,
            'joins': {k: next(iter(v)) for k, v in joins.items()},
            'required_property_records': s.count('AUDIT_REQ_BEGIN')}


def audit(queries):
    summaries = {}
    traces = {}
    for n in (3, 9):
        for cell, (e, o) in CELLS.items():
            with connect(e, o, trace=True) as db, db.cursor() as cur:
                pid = one(cur, 'SELECT pg_backend_pid()')
                plan = native_plan(cur, queries[n])
            # Backend lifetime ends before reading its C++ stream.
            path = LOG/'audit'/f'{pid}.log'
            t = parse_trace(path)
            traces[n, cell] = t
            assert t['policies'][-1] == (str(e), str(o), '0', '1')
            assert {x[1] for x in t['costs']} == {str(o)}, 'mixed cost models'
            assert {x[2] for x in t['costs']} == {'2'}, 'host count drift'
            assert {x[0] for x in t['costs']} == {'FULL', 'PARTIAL'}, 'missing full/partial repricing'
            assert t['required_property_records'] > 0
            save(f'audit/q{n:02d}-{cell}-plan.json', plan)
            summaries[f'q{n}-{cell}'] = {'backend_pid': pid, 'policy': t['policies'][-1],
                'disabled_xforms': t['disabled'], 'cost_calls': dict(Counter(x[0] for x in t['costs'])),
                'join_identities': len(t['joins']), 'property_records': t['required_property_records']}
        for a, b in [('W', 'E'), ('O', 'EO'), ('W', 'O'), ('E', 'EO')]:
            ta, tb = traces[n, a], traces[n, b]
            common = set(ta['joins']) & set(tb['joins'])
            assert common, 'no common hash join identities to validate P'
            assert all(ta['joins'][k] == tb['joins'][k] for k in common), 'E/O leaked into P request sets'
            summaries[f'q{n}-{a}-{b}-P'] = {'common_join_identities': len(common), 'request_differences': 0}
        for a, b in [('W', 'O'), ('E', 'EO')]:
            assert traces[n, a]['disabled'] == traces[n, b]['disabled'], 'O changed transform availability'
        assert traces[n, 'W']['disabled'] != traces[n, 'E']['disabled'], 'E inactive'
        with connect(-1, -1) as db, db.cursor() as cur:
            stock = native_plan(cur, queries[n])
        strong = json.loads((LOG/f'audit/q{n:02d}-EO-plan.json').read_text())
        assert stock['Plan'] == strong['Plan'], 'explicit strong policy differs from stock DPv1 path'
    fallback = []
    for e in (0, 1):
        with connect(e, 1, trace=True, mode='exhaustive2') as db, db.cursor() as cur:
            pid = one(cur, 'SELECT pg_backend_pid()')
            plan = native_plan(cur, queries[3])
        t = parse_trace(LOG/'audit'/f'{pid}.log')
        assert t['policies'][-1][2:] == ('1', '1')
        fallback.append((t['disabled'], plan['Plan']))
    assert fallback[0] == fallback[1], 'shared DPv2 fallback changed'
    summaries['shared_fallback_equal'] = True
    summaries['gate'] = 'AUDIT_PASS'
    save('audit-result.json', summaries)
    event('AUDIT_PASS')


def trial(n, query, expected, cell, repetition):
    e, o = CELLS[cell]
    started = time.monotonic()
    tag = f'r{repetition}-q{n:02d}-{cell}'
    with connect(e, o) as db, db.cursor() as cur:
        cur.execute('PREPARE pilot_query AS '+query)
        before = one(cur, "SELECT generic_plans FROM pg_prepared_statements WHERE name='pilot_query'")
        assert before == 0
        timed = native_plan(cur, 'EXECUTE pilot_query', analyze=True)
        save('plans/'+tag+'-timed.json', timed)
        after_first = one(cur, "SELECT generic_plans FROM pg_prepared_statements WHERE name='pilot_query'")
        assert after_first == 1
        first_cached = native_plan(cur, 'EXECUTE pilot_query')
        cur.execute('EXECUTE pilot_query')
        rows = cur.fetchall()
        receipt = compare_bags(expected, rows)
        second_cached = native_plan(cur, 'EXECUTE pilot_query')
        after = one(cur, "SELECT generic_plans FROM pg_prepared_statements WHERE name='pilot_query'")
        assert after == 4
        assert first_cached['Plan'] == second_cached['Plan'], 'cached plan changed during oracle check'
        # Compare estimated plan fields recursively with the timed plan. Every
        # key in the non-ANALYZE plan must still be present and identical.
        def subset(a, b):
            if isinstance(a, dict):
                return all(k in b and subset(v, b[k]) for k, v in a.items())
            if isinstance(a, list):
                return isinstance(b, list) and len(a) == len(b) and all(subset(x, y) for x, y in zip(a, b))
            return a == b
        assert subset(first_cached['Plan'], timed['Plan']), 'timed and result-producing physical plans differ'
        p, x = float(timed['Planning Time']), float(timed['Execution Time'])
        assert p >= 0 and x >= 0 and p+x > 0
        save('plans/'+tag+'-cached.json', first_cached)
        record = {'query': n, 'cell': cell, 'repetition': repetition,
                  'planning_ms': p, 'execution_ms': x, 'total_ms': p+x,
                  'generic_plan_uses': after, 'physical_plan_sha256': digest(first_cached['Plan']),
                  'wall_seconds': time.monotonic()-started, 'notices': db.notices, **receipt}
    with (LOG/'trials.jsonl').open('a') as f:
        f.write(encoded(record)+'\n')
    event('trial_complete', query=n, cell=cell, repetition=repetition)
    return record


def score(records):
    measured = [r for r in records if r['repetition'] > 0]
    assert len(measured) == 22*4*3
    q = {cell: -sum(math.log(r['total_ms']) for r in measured if r['cell'] == cell)/66 for cell in CELLS}
    gap = q['EO']-q['W']
    rep_gaps = []
    for rep in (1, 2, 3):
        qq = {cell: -sum(math.log(r['total_ms']) for r in measured if r['cell'] == cell and r['repetition'] == rep)/22 for cell in CELLS}
        rep_gaps.append(qq['EO']-qq['W'])
    result = {'native_objective': 'planning_ms+execution_ms', 'Q': q, 'G': gap,
              'geometric_speedup': math.exp(gap), 'repetition_gaps': rep_gaps,
              'correctness_green': True, 'audit_green': True, 'complete_measured_trials': len(measured),
              'recovery_E': None, 'recovery_O': None, 'scope': 'Two-factor TPC-H pilot; no expert-days, three-capability, or token-budget proof.'}
    if math.exp(gap) < 1.25 or any(g <= 0 for g in rep_gaps):
        result['decision'] = 'HOLD_HEADROOM_NOT_QUALIFIED'
    else:
        r = {cell: (q[cell]-q['W'])/gap for cell in ('E', 'O')}
        result.update(recovery_E=r['E'], recovery_O=r['O'],
                      leave_one_out_E=1-r['O'], leave_one_out_O=1-r['E'])
        if max(r.values()) >= .8:
            result['decision'] = 'STOP_SINGLETON_DOMINANCE'
        elif all(.1 <= v < .8 for v in r.values()) and min(1-r['E'], 1-r['O']) >= .1:
            result['decision'] = 'ELIGIBLE_FOR_NEXT_REVIEW'
        else:
            result['decision'] = 'HOLD_INSUFFICIENT_MATERIALITY'
    lookup = {(r['query'], r['cell'], r['repetition']): math.log(r['total_ms']) for r in measured}
    interactions = []
    rng = random.Random(20260917)
    for n in range(1, 23):
        values = [lookup[n,'W',rep]-lookup[n,'E',rep]-lookup[n,'O',rep]+lookup[n,'EO',rep] for rep in (1,2,3)]
        samples = sorted(sum(rng.choice(values) for _ in range(3))/3 for _ in range(2000))
        interactions.append({'query': n, 'log_interaction_by_repetition': values,
                             'mean_log_interaction': sum(values)/3,
                             'descriptive_bootstrap_95_interval': [samples[49],samples[1949]],
                             'warning': 'Only three repetitions; uncertainty estimate is weak.'})
    result['interactions'] = interactions
    save('pilot-result.json', result)
    event('pilot_complete', decision=result['decision'], speedup=result['geometric_speedup'],
          recovery_E=result['recovery_E'], recovery_O=result['recovery_O'])


def main():
    assert os.getuid() != 0
    save('manifest.json', {'original_protocol_sha256': ORIGINAL_PROTOCOL,
         'pilot_protocol_sha256': hashlib.sha256(Path('/protocol.md').read_bytes()).hexdigest(),
         'uid': os.getuid(), 'source': '8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4',
         'legacy_source': 'f031877bf0de737bbaa8138f8e4e46e57cdba50d', 'cells': CELLS})
    event('data_generation_begin')
    queries, expected = prepare_data()
    stats = statistics_snapshot()
    save('statistics-before.json', stats)
    event('data_ready', statistics_sha256=digest(stats))
    audit(queries)
    records = []
    rng = random.Random(20260917)
    schedule = []
    for rep in (0, 1, 2, 3):
        order = list(range(1, 23)); rng.shuffle(order)
        for n in order:
            cells = list(CELLS); rng.shuffle(cells)
            schedule.extend((rep,n,cell) for cell in cells)
    save('schedule.json', schedule)
    for rep, n, cell in schedule:
        event('trial_begin', query=n, cell=cell, repetition=rep)
        records.append(trial(n, queries[n], expected[n], cell, rep))
    after = statistics_snapshot()
    save('statistics-after.json', after)
    assert digest(stats) == digest(after), 'optimizer-visible statistics changed'
    score(records)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        save('failure.json', {'error_type': type(exc).__name__, 'error': str(exc),
                             'traceback': traceback.format_exc(), 'decision': 'HOLD_INCOMPLETE_OR_FAILED_GATE',
                             'recovery_E': None, 'recovery_O': None})
        event('pilot_failed', error=str(exc))
        raise
