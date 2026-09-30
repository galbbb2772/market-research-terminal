#!/usr/bin/env python3
"""Build MARKET-SNAPSHOT-V1 from approved MARKET-HISTORY-V1 data.

This tool never downloads market data. It validates a provider-neutral daily history
file and derives website metrics. `--publish` refuses any history whose
rights_status is not `verified_publishable`.
"""
from __future__ import annotations
import argparse,json,math,statistics
from pathlib import Path

PUBLISHABLE='verified_publishable'

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def canonical_ids(universe):
    ids={x['id'] for x in universe.get('benchmarks',[]) if x.get('id')}
    ids|={x['id'] for x in universe.get('major_indices',[]) if x.get('id')}
    for system in universe.get('sector_systems',{}).values():
        ids|={x['id'] for x in system.get('items',[]) if x.get('id')}
    return ids

def validate_bar(bar):
    if not isinstance(bar,list) or len(bar)<5 or len(bar)>7: raise ValueError('bar must have 5-7 fields')
    date=str(bar[0]); o,h,l,c=map(float,bar[1:5])
    if not date or not all(math.isfinite(x) for x in (o,h,l,c)): raise ValueError('invalid OHLC')
    if h<l or h<max(o,c) or l>min(o,c): raise ValueError(f'inconsistent OHLC on {date}')
    if len(bar)>5 and bar[5] is not None and float(bar[5])<0: raise ValueError(f'negative volume on {date}')
    return date

def validate_history(history,allowed_ids):
    if history.get('schema')!='MARKET-HISTORY-V1': raise ValueError('schema must be MARKET-HISTORY-V1')
    inst=history.get('instruments')
    if not isinstance(inst,dict) or not inst: raise ValueError('history has no instruments')
    unknown=set(inst)-allowed_ids
    if unknown: raise ValueError(f'non-canonical instruments: {sorted(unknown)}')
    for symbol,item in inst.items():
        bars=item.get('bars',[])
        if not bars: raise ValueError(f'{symbol}: empty bars')
        dates=[validate_bar(b) for b in bars]
        if dates!=sorted(dates) or len(dates)!=len(set(dates)): raise ValueError(f'{symbol}: dates must be unique ascending')
    return inst

def price(bar):
    if len(bar)>6 and bar[6] is not None:
        v=float(bar[6]);
        if math.isfinite(v) and v>0:return v
    return float(bar[4])

def ret(bars,n):
    if len(bars)<=n:return None
    a,b=price(bars[-1-n]),price(bars[-1])
    return (b/a-1)*100 if a else None

def vol20(bars):
    use=bars[-21:]
    rr=[]
    for a,b in zip(use,use[1:]):
        p0,p1=price(a),price(b)
        if p0:rr.append(p1/p0-1)
    return statistics.stdev(rr)*math.sqrt(252)*100 if len(rr)>1 else None

def drawdown(bars):
    values=[price(b) for b in bars]
    peak=max(values)
    return (values[-1]/peak-1)*100 if peak else None

def percentile(latest,prior):
    vals=[float(x) for x in prior if x is not None and math.isfinite(float(x))]
    if latest is None or not vals:return None
    return sum(v<=latest for v in vals)/len(vals)*100

def activity(bars):
    use=bars[-61:]
    if len(use)<6:return None
    dv=[];rng=[]
    for b in use:
        c=float(b[4]); h=float(b[2]); l=float(b[3]); v=b[5] if len(b)>5 else None
        dv.append(c*float(v) if v is not None and c>0 else None)
        rng.append((h-l)/c*100 if c>0 else None)
    scores=[]
    p=percentile(dv[-1],dv[:-1])
    if p is not None:scores.append(p)
    p=percentile(rng[-1],rng[:-1])
    if p is not None:scores.append(p)
    return sum(scores)/len(scores) if scores else None

def structure_state(symbol,last_close,structure):
    item=(structure or {}).get('instruments',{}).get(symbol,{})
    boxes=item.get('boxes') or []
    if not boxes:return None
    b=boxes[-1]; lo=b.get('lower'); hi=b.get('upper')
    if lo is None or hi is None:return None
    if last_close<float(lo):return 'below_box'
    if last_close>float(hi):return 'above_box'
    return 'inside_box'

def build(history,universe,structure=None):
    inst=validate_history(history,canonical_ids(universe))
    spy=inst.get('SPY',{}).get('bars',[])
    spy20=ret(spy,20) if spy else None
    rows=[]
    for symbol,item in inst.items():
        bars=item['bars']; r20=ret(bars,20)
        row={
            'id':symbol,'date':bars[-1][0],'close':float(bars[-1][4]),
            'return_1d':ret(bars,1),'return_5d':ret(bars,5),'return_20d':r20,
            'volatility_20d':vol20(bars),'drawdown_from_peak':drawdown(bars),
            'relative_to_spy_20d':(r20-spy20) if r20 is not None and spy20 is not None else None,
            'activity_score':activity(bars),'range_box_state':structure_state(symbol,float(bars[-1][4]),structure)
        }
        rows.append(row)
    dates=[r['date'] for r in rows]
    return {'schema':'MARKET-SNAPSHOT-V1','as_of':max(dates) if dates else None,'provider':history.get('provider'),'rights_status':history.get('rights_status','pending_review'),'rows':rows,'notes':['activity_score is a volume/range percentile proxy, not fund flow','returns prefer adjusted_close when supplied']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--universe',default='docs/data/market_universe.json');ap.add_argument('--structure');ap.add_argument('--output',default='/tmp/market_snapshot.json');ap.add_argument('--publish',action='store_true');args=ap.parse_args()
    h,u=load(args.input),load(args.universe);s=load(args.structure) if args.structure and Path(args.structure).exists() else None
    if args.publish and h.get('rights_status')!=PUBLISHABLE:raise SystemExit('refusing publish: market history is not verified_publishable')
    out=build(h,u,s);path=Path(args.output)
    if args.publish and path.as_posix()!='/tmp/market_snapshot.json' and 'docs/data/' not in path.as_posix():raise SystemExit('publish output must be under docs/data/')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(f'wrote {path} ({len(out["rows"])} instruments)')
if __name__=='__main__':main()
