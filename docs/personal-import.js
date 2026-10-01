(()=>{'use strict';
const $=id=>document.getElementById(id);
const EXPECTED='MRT-TIINGO-PERSONAL-BUNDLE-V1';
const ALLOWED=['SPY','QQQ','DIA','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY'];
function fail(msg){$('importStatus').innerHTML='<span class="pd-bad">导入失败：</span>'+msg}
async function loadFile(file){if(!file)return;try{let text=await file.text();if(text.length>80_000_000)throw Error('文件过大，拒绝读取');let x=JSON.parse(text);if(x?.schema!==EXPECTED)throw Error('不是本项目的 Tiingo Personal Bundle V1');if(x?.provider!=='Tiingo EOD')throw Error('数据源标识不是 Tiingo EOD');if(!x?.data||typeof x.data!=='object')throw Error('缺少 data 字段');let keys=Object.keys(x.data);let bad=keys.filter(k=>!ALLOWED.includes(k));if(bad.length)throw Error('包含未允许标的：'+bad.slice(0,5).join(', '));let present=ALLOWED.filter(s=>Array.isArray(x.data[s])&&x.data[s].length);if(!present.length)throw Error('没有可用日K');$('importStatus').innerHTML=`<span class="pd-ok">Bundle 验证通过</span>：${present.length}/${ALLOWED.length} 个标的，${x.start||'—'} → ${x.end||'—'}。正在进入研究链…`;window.dispatchEvent(new CustomEvent('mrt-personal-import',{detail:{data:x.data}}));}catch(e){fail(e.message||String(e))}}
$('bundleFile').addEventListener('change',e=>loadFile(e.target.files?.[0]));
let dz=$('bundleDrop');
for(let ev of ['dragenter','dragover'])dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add('pd-drop-on')});
for(let ev of ['dragleave','drop'])dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove('pd-drop-on')});
dz.addEventListener('drop',e=>loadFile(e.dataTransfer?.files?.[0]));
})();
