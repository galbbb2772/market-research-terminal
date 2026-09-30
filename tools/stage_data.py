"""Opt-in staging for an ALREADY ACQUIRED, licensed structure_lab.json file.

Never fetch or invent observations. Does not prove vendor license or PIT vintage.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path

def validate(obj):
    if not isinstance(obj,dict) or obj.get('schema')!='STRUCTURE-LAB-V1':
        raise ValueError('Expected STRUCTURE-LAB-V1 object')
    instruments=obj.get('instruments')
    if not isinstance(instruments,dict) or not instruments:
        raise ValueError('Missing real instruments; no sample histories allowed')
    for ticker,item in instruments.items():
        bars=item.get('bars') or []
        if not isinstance(bars,list) or len(bars)<2:
            raise ValueError(f'{ticker}: missing source bars')
        days=[]
        for b in bars:
            if not isinstance(b,list) or len(b)<6:
                raise ValueError(f'{ticker}: bad OHLCV row')
            day,op,hi,lo,close,vol=b[:6]
            if not (isinstance(day,str) and len(day)==10):
                raise ValueError(f'{ticker}: invalid date')
            if not all(isinstance(v,(float,int)) and not isinstance(v,bool) for v in (op,hi,lo,close,vol)):
                raise ValueError(f'{ticker}: nonnumeric OHLCV')
            if not (hi>=max(op,close,lo) and lo<=min(op,close,hi) and lo>0 and vol>=0):
                raise ValueError(f'{ticker}: invalid OHLCV')
            days.append(day)
        if days!=sorted(set(days)):
            raise ValueError(f'{ticker}: unsorted or duplicate dates')
        for box in item.get('boxes') or []:
            if not all(x in box for x in ('id','start_at','detected_at','upper','lower','scores')):
                raise ValueError(f'{ticker}: incomplete box')
            if box['start_at']>box['detected_at'] or box['lower']>box['upper']:
                raise ValueError(f'{ticker}: invalid box timeline or bounds')
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',help='locally obtained real dataset JSON (no API fetch)')
    p.add_argument('--output',default='docs/data/structure_lab.json')
    p.add_argument('--stage',action='store_true',help='actually write after rights check')
    args=p.parse_args()
    data=json.loads(Path(args.source).read_text(encoding='utf-8'))
    validate(data)
    if not args.stage:
        print('Validated schema and observed rows. Dry-run only; no data published.')
        return
    if os.environ.get('DATA_RIGHTS_APPROVED')!='true' or os.environ.get('WEBSITE_DEPLOY_AUTHORIZED')!='true':
        raise SystemExit('Missing BOTH approval environment variables. No public write.')
    target=Path(args.output)
    if target.resolve().name!='structure_lab.json':
        raise SystemExit('Refusing to overwrite an unexpected file')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Staged approved real dataset at',target)

if __name__=='__main__':main()
