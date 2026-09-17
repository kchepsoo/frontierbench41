#!/usr/bin/env python3
"""Counterexamples for the oracle and gate; never benchmark evidence."""
from decimal import Decimal
from pathlib import Path
import importlib.util
import json
import tempfile
spec=importlib.util.spec_from_file_location('pilot', Path(__file__).with_name('run-pilot.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
p.compare_bags([(None, Decimal('2')), (None, Decimal('2'))], [(None, 2.0), (None, 2.000000001)])
for a,b in [([(1,),(1,)],[(1,)]), ([(None,)],[(0,)]), ([(Decimal('2'),)],[(2.01,)])]:
    try:p.compare_bags(a,b)
    except AssertionError:pass
    else:raise AssertionError('oracle accepted a counterexample')
with tempfile.TemporaryDirectory() as d:
    p.LOG=Path(d)
    # A faster singleton without qualified EO/W headroom must not get a score.
    records=[{'query':n,'cell':cell,'repetition':rep,'total_ms':{'W':100,'E':50,'O':95,'EO':99}[cell]}
             for n in range(1,23) for cell in p.CELLS for rep in (1,2,3)]
    p.score(records)
    result=json.loads((p.LOG/'pilot-result.json').read_text())
    assert result['decision']=='HOLD_HEADROOM_NOT_QUALIFIED'
    assert result['recovery_E'] is None and result['recovery_O'] is None
    # Prespecified dominance must stop even when the other singleton is useful.
    for r in records:r['total_ms']={'W':100,'E':53,'O':80,'EO':50}[r['cell']]
    p.score(records)
    result=json.loads((p.LOG/'pilot-result.json').read_text())
    assert result['decision']=='STOP_SINGLETON_DOMINANCE'
print('HARNESS_COUNTEREXAMPLES_PASS; synthetic inputs are not workload evidence')
