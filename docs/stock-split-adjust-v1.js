(()=>{'use strict';
const DB_NAME='mrt-personal-local-data',DB_VERSION=1,STORE='bundles';
const COMMON=[2,3,4,5,6,7,8,10,12,15,20];
const finite=x=>Number.isFinite(Number(x));
function nearestRatio(x){let best=null,err=Infinity;for(const n of COMMON){let e=Math.abs(x/n-1);if(e<err){err=e;best=n}}return err<=.16?best:null}
function cloneBar(b){return{...b,o:+b.o,h:+b.h,l:+b.l,c:+b.c,v:b.v==null?null:+b.v}}
function detectEvent(prev,cur){if(!prev||!cur||!finite(prev.c)||!finite(cur.c)||prev.c<=0||cur.c<=0)return null;
  let r=prev.c/cur.c;
  if(r>1.55){let n=nearestRatio(r);if(n){let adjustedPrev=prev.c/n,move=Math.abs(cur.c/adjustedPrev-1);if(move<=.28)return{type:'forward',ratio:n,move}}}
  r=cur.c/prev.c;
  if(r>1.55){let n=nearestRatio(r);if(n){let adjustedPrev=prev.c*n,move=Math.abs(cur.c/adjustedPrev-1);if(move<=.28)return{type:'reverse',ratio:n,move}}}
  return null}
function adjustBars(rows){if(!Array.isArray(rows)||rows.length<2)return{bars:rows||[],events:[]};let a=rows.map(cloneBar).sort((x,y)=>String(x.date).localeCompare(String(y.date))),events=[];
  for(let i=1;i<a.length;i++){
    let ev=detectEvent(a[i-1],a[i]);if(!ev)continue;
    let f=ev.type==='forward'?1/ev.ratio:ev.ratio,volF=ev.type==='forward'?ev.ratio:1/ev.ratio;
    for(let j=0;j<i;j++){
      for(let k of ['o','h','l','c'])if(finite(a[j][k]))a[j][k]*=f;
      if(finite(a[j].v))a[j].v*=volF;
    }
    events.push({date:a[i].date,type:ev.type,ratio:ev.ratio,move:ev.move});
  }
  return{bars:a,events};
}
function openDB(){return new Promise((resolve,reject)=>{let r=indexedDB.open(DB_NAME,DB_VERSION);r.onupgradeneeded=()=>{let db=r.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE)};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error||Error('IndexedDB unavailable'))})}
async function run(){let db=await openDB();let keys=await new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readonly'),r=tx.objectStore(STORE).getAllKeys();r.onsuccess=()=>resolve(r.result||[]);r.onerror=()=>reject(r.error)}),changed=[];
  for(const key of keys){if(typeof key!=='string'||!key.startsWith('stock:'))continue;let rec=await new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readonly'),r=tx.objectStore(STORE).get(key);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error)});if(!rec?.bars?.length||rec.priceBasis==='split-adjusted-v1')continue;let out=adjustBars(rec.bars);if(!out.events.length){rec.priceBasis='split-adjusted-v1';rec.splitEvents=[]}else{rec.bars=out.bars;rec.priceBasis='split-adjusted-v1';rec.splitEvents=out.events;changed.push({key,events:out.events})}await new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(rec,key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error)})}
  window.__mrtSplitAdjustInfo=changed;return changed}
window.__mrtSplitAdjustReady=run().catch(e=>{console.warn('split adjust skipped',e);return[]});
})();