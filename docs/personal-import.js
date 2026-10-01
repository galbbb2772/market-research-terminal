(()=>{'use strict';
const $=id=>document.getElementById(id);
const EXPECTED='MRT-TIINGO-PERSONAL-BUNDLE-V1';
const ALLOWED=['SPY','QQQ','DIA','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
const DB_NAME='mrt-personal-local-data';
const DB_VERSION=1;
const STORE='bundles';
const DEFAULT_KEY='default-tiingo-bundle';
let dbPromise=null;
function fail(msg){$('importStatus').innerHTML='<span class="pd-bad">导入失败：</span>'+msg}
function openDB(){if(!('indexedDB' in window))return Promise.reject(Error('这个浏览器不支持本机持久存储'));if(dbPromise)return dbPromise;dbPromise=new Promise((resolve,reject)=>{let req=indexedDB.open(DB_NAME,DB_VERSION);req.onupgradeneeded=()=>{let db=req.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE)};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error||Error('IndexedDB 打开失败'))});return dbPromise}
async function dbGet(){let db=await openDB();return new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readonly'),req=tx.objectStore(STORE).get(DEFAULT_KEY);req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>reject(req.error||Error('读取常用 Bundle 失败'))})}
async function dbPut(bundle,fileName='tiingo_personal_bundle.json'){let db=await openDB();let record={bundle,fileName,savedAt:new Date().toISOString()};await new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(record,DEFAULT_KEY);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error||Error('保存常用 Bundle 失败'));tx.onabort=()=>reject(tx.error||Error('保存常用 Bundle 被中止'))});try{if(navigator.storage?.persist)await navigator.storage.persist()}catch(_){}}
async function dbDelete(){let db=await openDB();await new Promise((resolve,reject)=>{let tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).delete(DEFAULT_KEY);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error||Error('清除常用 Bundle 失败'));tx.onabort=()=>reject(tx.error||Error('清除常用 Bundle 被中止'))})}
function validate(x){if(x?.schema!==EXPECTED)throw Error('不是本项目的 Tiingo Personal Bundle V1');if(x?.provider!=='Tiingo EOD')throw Error('数据源标识不是 Tiingo EOD');if(!x?.data||typeof x.data!=='object')throw Error('缺少 data 字段');let keys=Object.keys(x.data),bad=keys.filter(k=>!ALLOWED.includes(k));if(bad.length)throw Error('包含未允许标的：'+bad.slice(0,5).join(', '));let present=ALLOWED.filter(s=>Array.isArray(x.data[s])&&x.data[s].length);if(!present.length)throw Error('没有可用日K');return present}
function publish(x,source){let present=validate(x);$('importStatus').innerHTML=`<span class="pd-ok">${source}</span>：${present.length}/${ALLOWED.length} 个标的，${x.start||'—'} → ${x.end||'—'}。正在进入研究链…`;window.dispatchEvent(new CustomEvent('mrt-personal-import',{detail:{data:x.data}}));return present}
function fmtTime(s){if(!s)return '—';let d=new Date(s);return Number.isNaN(d.getTime())?s:d.toLocaleString()}
function setSavedStatus(record){let el=$('savedBundleStatus'),use=$('useSavedBundle'),forget=$('forgetSavedBundle');if(!el)return;if(record?.bundle){let b=record.bundle,present=ALLOWED.filter(s=>Array.isArray(b?.data?.[s])&&b.data[s].length);el.innerHTML=`<span class="pd-ok">已记住常用 Bundle</span>：${record.fileName||'tiingo_personal_bundle.json'} · ${present.length}/${ALLOWED.length} 标的 · ${b.start||'—'} → ${b.end||'—'} · 保存于 ${fmtTime(record.savedAt)}。以后打开本页会自动载入。`;if(use)use.disabled=false;if(forget)forget.disabled=false}else{el.textContent='当前没有已记住的常用 Bundle。第一次导入时保持“设为常用 Bundle”勾选即可。';if(use)use.disabled=true;if(forget)forget.disabled=true}}
async function loadFile(file){if(!file)return;try{if(file.size>80_000_000)throw Error('文件过大，拒绝读取');let text=await file.text();if(text.length>80_000_000)throw Error('文件过大，拒绝读取');let x=JSON.parse(text),present=validate(x);if($('rememberBundle')?.checked){await dbPut(x,file.name||'tiingo_personal_bundle.json');setSavedStatus(await dbGet());$('importStatus').innerHTML=`<span class="pd-ok">已设为常用 Bundle</span>：${present.length}/${ALLOWED.length} 个标的，${x.start||'—'} → ${x.end||'—'}。以后打开本页会自动载入；正在进入研究链…`;window.dispatchEvent(new CustomEvent('mrt-personal-import',{detail:{data:x.data}}))}else publish(x,'Bundle 验证通过')}catch(e){fail(e.message||String(e))}}
async function useSaved(auto=false){try{let record=await dbGet();setSavedStatus(record);if(!record?.bundle){if(!auto)fail('还没有已记住的常用 Bundle');return}publish(record.bundle,auto?'已自动载入常用 Bundle':'已载入常用 Bundle')}catch(e){if(auto){$('savedBundleStatus').innerHTML='<span class="pd-bad">无法读取常用 Bundle：</span>'+(e.message||String(e))}else fail(e.message||String(e))}}
async function forgetSaved(){try{await dbDelete();setSavedStatus(null);$('importStatus').textContent='已忘记常用 Bundle；当前已经进入研究链的数据不会被立即清空。'}catch(e){fail(e.message||String(e))}}
$('bundleFile').addEventListener('change',e=>loadFile(e.target.files?.[0]));
let dz=$('bundleDrop');
for(let ev of ['dragenter','dragover'])dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('pd-drop-on')});
for(let ev of ['dragleave','drop'])dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('pd-drop-on')});
dz.addEventListener('drop',e=>loadFile(e.dataTransfer?.files?.[0]));
$('useSavedBundle')?.addEventListener('click',()=>useSaved(false));
$('forgetSavedBundle')?.addEventListener('click',forgetSaved);
setSavedStatus(null);
useSaved(true);
})();
