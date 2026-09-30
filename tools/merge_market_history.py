#!/usr/bin/env python3
"""Merge provider-specific MARKET-HISTORY-V1 files into one website history file.

Overlay instruments replace matching base instruments. Public output is allowed only
when every participating source declares verified_publishable. The merger annotates
per-instrument provider/provenance so mixed ETF/index sources stay traceable.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

PUBLISHABLE = 'verified_publishable'


def load_optional(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def validate_doc(doc, label):
    if not doc:
        return
    if doc.get('schema') != 'MARKET-HISTORY-V1':
        raise ValueError(f'{label}: schema must be MARKET-HISTORY-V1')
    if not isinstance(doc.get('instruments'), dict) or not doc['instruments']:
        raise ValueError(f'{label}: no instruments')


def annotate(doc):
    d = copy.deepcopy(doc)
    provider = d.get('provider')
    licence = d.get('license_reference')
    for item in d.get('instruments', {}).values():
        item.setdefault('provider', provider)
        if licence:
            item.setdefault('license_reference', licence)
    return d


def merge(base, overlays, publish=False):
    docs = [d for d in [base, *overlays] if d]
    if not docs:
        raise ValueError('no market history documents supplied')
    for i, doc in enumerate(docs):
        validate_doc(doc, f'document {i + 1}')
    if publish:
        bad = [d.get('provider') or 'unknown' for d in docs if d.get('rights_status') != PUBLISHABLE]
        if bad:
            raise ValueError(f'cannot publish: non-publishable source(s): {bad}')
    result = {
        'schema': 'MARKET-HISTORY-V1',
        'provider': 'mixed' if len(docs) > 1 else docs[0].get('provider'),
        'rights_status': PUBLISHABLE if all(d.get('rights_status') == PUBLISHABLE for d in docs) else 'verified_internal_only',
        'adjustment': 'per-instrument; see provider metadata',
        'instruments': {},
        'sources': [],
        'notes': ['Merged provider-neutral website history; per-instrument provider metadata is authoritative.'],
    }
    for doc in docs:
        d = annotate(doc)
        result['sources'].append({
            'provider': d.get('provider'),
            'rights_status': d.get('rights_status'),
            'license_reference': d.get('license_reference'),
            'retrieved_at_utc': d.get('retrieved_at_utc'),
        })
        for symbol, item in d['instruments'].items():
            result['instruments'][symbol] = item
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base')
    p.add_argument('--overlay', action='append', default=[])
    p.add_argument('--output', required=True)
    p.add_argument('--publish', action='store_true')
    a = p.parse_args(argv)
    base = load_optional(a.base) if a.base else None
    overlays = [load_optional(x) for x in a.overlay]
    if any(x is None for x in overlays):
        missing = [path for path, doc in zip(a.overlay, overlays) if doc is None]
        p.error(f'missing overlay file(s): {missing}')
    out = merge(base, overlays, publish=a.publish)
    target = Path(a.output)
    if a.publish and not target.resolve().is_relative_to(Path('docs/data').resolve()):
        p.error('--publish output must be under docs/data')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Merged {len(out["instruments"])} instruments from {len(out["sources"])} source documents -> {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
