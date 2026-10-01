(()=>{'use strict';
const $=id=>document.getElementById(id);
function correctHealthcareAutoMap(){let status=$('mappingStatus'),sector=$('sectorPick');if(!status||!sector||!status.textContent.includes('自动映射'))return;let themes=[...document.querySelectorAll('#themeChecks input:checked')].map(x=>x.value);if(sector.value==='XLK'&&(themes.includes('XBI')||themes.includes('ARKG'))){sector.value='XLV';status.innerHTML=status.innerHTML.replace('行业 XLK','行业 XLV')+' <span class="st-note">（生物科技/基因科技优先归入医疗保健）</span>';sector.dispatchEvent(new Event('change'))}}
let status=$('mappingStatus');if(status)new MutationObserver(correctHealthcareAutoMap).observe(status,{childList:true,subtree:true,characterData:true});
function loadIntervalV2(){if(document.querySelector('script[data-stock-interval-v2]'))return;let s=document.createElement('script');s.dataset.stockIntervalV2='1';s.src='./stock-interval-v2.js?v=20261001-v3';s.onload=()=>window.dispatchEvent(new Event('resize'));document.head.appendChild(s)}
loadIntervalV2();
let q=(new URLSearchParams(location.search).get('symbol')||'').trim().toUpperCase();if(/^[A-Z0-9.\-]{1,12}$/.test(q)){let ticker=$('ticker');if(ticker)ticker.value=q;setTimeout(()=>{$('useSaved')?.click()},0)}
})();