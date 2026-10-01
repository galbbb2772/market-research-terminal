(()=>{'use strict';
const $=id=>document.getElementById(id);
const f=(v,d=3)=>v==null?'—':Number(v).toFixed(d);
const stat=(label,value,note='',klass='')=>`<div class="stat ${klass}"><small>${label}</small><b>${value}</b><small>${note}</small></div>`;
function verdict(status){return status==='survives_current_checks'?['保留候选','通过研究级全局FDR与时间稳定性门槛','ok']:status==='not_supported_after_correction'?['未获支持','校正后不保留','no']:['样本不足','无法完成严格检验','']}
function mount(){
  const anchor=$('activityPersistence');
  if(!anchor||$('rtActivityValidation'))return;
  const activityPanel=anchor.closest('.panel');
  if(!activityPanel)return;
  const panel=document.createElement('section');
  panel.id='rtActivityValidation';
  panel.className='panel';
  panel.innerHTML='<h2>活跃度排名持续性｜严格显著性验证</h2><div id="rtActivityValidationSummary" class="grid"></div><div id="rtActivityValidationTable" class="scroll" style="margin-top:12px"></div><p class="small">检验对象是每天完整行业活跃度横截面的排名，而不是只对三个汇总均值做检验。1/5/20交易日 Spearman 分别经过三段连续历史、5交易日块置换、5交易日 moving-block bootstrap、活跃度家族FDR，以及与收益周期假设合并后的研究级全局FDR。通过仍只代表历史依赖候选，不代表未来可预测或可交易。</p>';
  activityPanel.insertAdjacentElement('afterend',panel);
  document.querySelectorAll('.stat').forEach(card=>{
    const first=card.querySelector('small');
    if(first?.textContent.trim()==='活跃度显著性'){
      const b=card.querySelector('b'),smalls=card.querySelectorAll('small');
      if(b)b.textContent='已接入';
      if(smalls[1])smalls[1].textContent='1/5/20日均已进入严格验证层';
    }
  });
  renderWaiting();
  fetch('./data/structure_lab.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('研究数据尚未正式发布');return r.json()}).then(render).catch(err=>{
    $('rtActivityValidationSummary').innerHTML=stat('严格活跃度验证','等待真实数据',err.message||'尚无公开行情');
    $('rtActivityValidationTable').innerHTML='';
  });
}
function renderWaiting(){
  $('rtActivityValidationSummary').innerHTML=stat('严格活跃度验证','读取中','等待 cycle_validation.activity_rank_persistence');
}
function render(data){
  const root=data?.cycle_validation?.activity_rank_persistence;
  if(!root){throw Error('严格活跃度验证尚未生成')}
  const summary=root.summary||{},rows=root.lags||[];
  $('rtActivityValidationSummary').innerHTML=[
    stat('检验滞后',rows.length?rows.map(r=>r.lag_sessions+'日').join(' / '):'—','固定 1 / 5 / 20 交易日'),
    stat('活跃度家族FDR保留',summary.activity_family_fdr_survivors??'—','BH · 仅1/5/20三项'),
    stat('研究级全局FDR保留',summary.research_global_fdr_survivors??'—','与收益周期全部假设合并校正'),
    stat('再过时间稳定性',summary.stable_research_global_survivors??'—',`${root.observations??'—'}日 · ${root.block_sessions??5}日block · ${root.resamples??'—'}次重采样`)
  ].join('');
  if(!rows.length){$('rtActivityValidationTable').innerHTML='<div class="small">样本不足，尚无可检验的活跃度排名持续性。</div>';return}
  $('rtActivityValidationTable').innerHTML='<table><tr><th>滞后</th><th>平均Spearman</th><th>有效对</th><th>块置换 p</th><th>活跃度 q</th><th>研究全局 q</th><th>95% bootstrap CI</th><th>三段均值</th><th>结论</th></tr>'+rows.map(r=>{
    const ci=r.bootstrap_ci95||[],splits=(r.split_mean_spearman||[]).map(x=>x==null?'—':f(x,3)).join(' / '),v=verdict(r.status);
    return `<tr><td>${r.lag_sessions}日</td><td>${f(r.observed_mean_spearman,3)}</td><td>${r.pairs??'—'}</td><td>${f(r.block_permutation_p,4)}</td><td>${f(r.q_activity_family,4)}</td><td>${f(r.q_research_global,4)}</td><td>${f(ci[0],3)} ～ ${f(ci[1],3)}</td><td>${splits}</td><td><span class="${v[2]}">${v[0]}</span></td></tr>`
  }).join('')+'</table>';
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
