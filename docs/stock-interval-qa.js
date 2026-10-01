(()=>{'use strict';
const KEY='mrt-stock-interval-qa-v1';
const CASES=['AAPL','NVDA','MSFT','GOOGL','META','AMZN','TSLA','AMD','CVS','UPS','SPY','QQQ'];
const $=id=>document.getElementById(id);
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(_){return{}}}
function save(x){localStorage.setItem(KEY,JSON.stringify(x))}
function current(){return ($('ticker')?.value||'').trim().toUpperCase()}
function statusLabel(v){return v==='ok'?'合理':v==='miss'?'漏识别':v==='false'?'误识别':v==='data'?'数据异常':'未验收'}
function color(v){return v==='ok'?'#86d5a0':v==='miss'||v==='false'?'#f3c987':v==='data'?'#f0a3a3':'#9db7c8'}
function install(){if(document.getElementById('intervalQaPanel'))return;let chart=$('stockChart'),sec=chart?.closest('section');if(!sec)return;let panel=document.createElement('section');panel.className='mp-panel';panel.id='intervalQaPanel';panel.innerHTML=`<div class="mp-toolbar"><h2 style="margin:0">区间算法验收集</h2><span id="qaSummary" class="mp-source"></span></div><p class="st-note">先冻结“什么叫区间”的规则，再谈回测。建议逐只检查：趋势停顿是否被误画、明显震荡是否漏掉、拆股后历史是否连续。</p><div id="qaCases" class="st-theme" style="margin:10px 0"></div><div class="mp-toolbar"><button data-qa="ok">✓ 识别合理</button><button data-qa="miss">漏掉区间</button><button data-qa="false">误画区间</button><button data-qa="data">数据异常</button><button id="qaNext">下一只</button></div><div class="st-data-actions" style="margin-top:10px"><input id="qaNote" class="st-input" style="min-width:min(620px,100%)" placeholder="备注：例如 2024Q2 低位平台漏掉 / 趋势中继不应算区间"><button id="qaSaveNote">保存备注</button><button id="qaExport">导出验收 JSON</button></div>`;sec.insertAdjacentElement('afterend',panel);
 let data=load();
 function render(){let s=current(),done=CASES.filter(x=>data[x]?.status).length,ok=CASES.filter(x=>data[x]?.status==='ok').length;$('qaSummary').textContent=`已验收 ${done}/${CASES.length} · 合理 ${ok}`;$('qaCases').innerHTML=CASES.map(sym=>{let v=data[sym]?.status;return `<button data-qa-symbol="${sym}" style="border-color:${color(v)};${sym===s?'outline:1px solid #e7f1f6;':''}">${sym} · ${statusLabel(v)}</button>`}).join('');$('qaNote').value=data[s]?.note||''}
 function select(sym){let t=$('ticker');if(t)t.value=sym;$('useSaved')?.click();setTimeout(render,120)}
 panel.addEventListener('click',e=>{let b=e.target.closest('[data-qa-symbol]');if(b){select(b.dataset.qaSymbol);return}let q=e.target.closest('[data-qa]');if(q){let s=current();if(!s)return;data[s]={...(data[s]||{}),status:q.dataset.qa,updatedAt:new Date().toISOString()};save(data);render();return}});
 $('qaSaveNote').onclick=()=>{let s=current();if(!s)return;data[s]={...(data[s]||{}),note:$('qaNote').value.trim(),updatedAt:new Date().toISOString()};save(data);render()};
 $('qaNext').onclick=()=>{let s=current(),i=Math.max(0,CASES.indexOf(s)),next=CASES.slice(i+1).find(x=>!data[x]?.status)||CASES.find(x=>!data[x]?.status)||CASES[(i+1)%CASES.length];select(next)};
 $('qaExport').onclick=()=>{let payload={schema:'MRT-STOCK-INTERVAL-QA-V1',createdAt:new Date().toISOString(),cases:CASES,results:data};let blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='stock-interval-qa.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
 let ticker=$('ticker');if(ticker){ticker.addEventListener('change',render);ticker.addEventListener('input',()=>setTimeout(render,0))}render()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();