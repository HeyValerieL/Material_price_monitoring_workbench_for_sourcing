(()=>{'use strict';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),fmt=n=>Number.isFinite(n)?n.toLocaleString('zh-CN',{maximumFractionDigits:1}):'—';
const statusNames={public:'公开 public',partial:'部分公开 partial',unverified:'未核实 unverified',paywalled:'登录／付费 paywalled'};
let ledger,rows=[],analysisData,contextData;
function previous(month,n){const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m-1-n,1)).toISOString().slice(0,7);}
function change(row,n){const base=rows.find(r=>r.month===previous(row.month,n));return base?(row.price/base.price-1)*100:null;}
function pct(v){return v===null?'—':(v>0?'+':'')+fmt(v)+'%';}
function render(){
const month=$('month').value,row=rows.find(r=>r.month===month);
$('price-value').textContent=row?fmt(row.price):'—';
$('price-note').textContent=row?'观察区间 '+row.period:'缺少该月下旬值；不使用上、中旬代替';
$('mom').textContent=row?pct(change(row,1)):'—';$('qoq').textContent=row?pct(change(row,3)):'—';
$('price-source').innerHTML=row?'<a target="_blank" rel="noopener" href="'+esc(row.source)+'">查看此月原始发布 ↗</a> · 国家统计局原始发布':'该月未采集完整月度观察，留空等待核验。';
$('coverage').textContent='所选 '+month+' · 历史记录 '+rows.length+' 个月 · 最新记录 '+(rows.at(-1)?.month||'无');
chart(month);

const delta=row?change(row,1):null,trend=MaterialPriceTrend.classify(rows,month);
$('trend').textContent=trend;$('trend-note').textContent=delta===null?'缺少同口径上月价格':'较上月 '+pct(delta)+'；前两个月连续上涨后下跌称为回调，其余下跌为下行';
renderAnalysis(month,row);
if(document.body.dataset.category==='aluminum')document.dispatchEvent(new CustomEvent('market-selection',{detail:{category:'aluminum',month}}));
const cards=delta!==null&&delta>0?[
['对确定订单分批单边锁价','对交付已确认、铝价传导较快的关键零部件，考虑与供应商协商固定材料价格或封顶条款，先覆盖近期交付批次，再视库存和报价变化追加；保留未锁部分应对回调。','价格保护'],
['提前锁量，分段确认价格','提前确认关键零部件订单的排产与交付量，可采用锁量不锁价或锁量加分批锁价，降低涨价期间供给与交付的不确定性；不额外扩大未确认需求。','交付保障'],
['缩短敞口，保留回调窗口','将长交期订单拆成多个定价窗口，优先处理调价传导快、替代难的零部件；供应恢复或铝锭库存转为累积时，放慢后续锁价，避免一次锁定全部远期高价。','节奏调整']
]:delta!==null&&delta<0?[
['复核前期涨价，推动降价落地','铝价回落时，优先复核前期已接受涨价的铝件报价；依据合同计价窗口、实际用铝量和同口径铝基准变化，推动未交付及后续订单下调材料价格，不把铝价跌幅直接等同零部件降价幅度。','降价传导'],
['锁量保交付，保留价格下调空间','对确定订单先锁数量和交期，价格采用分批点价、随基准向下调整，或经双方约定的封顶且可下调条款；明确适用批次、触发条件和结算窗口，避免一次固定全部远期价格。','定价弹性'],
['分批补库，保留后续议价窗口','按已确认排产分批补库，保障关键零部件交付；对未确认的远期需求保留定价弹性。若报价企稳、客户排产上调或交期拉长，再调整采购覆盖范围。','采购节奏']
]:[
['分批定价保留选择','短期缺少明确趋势，已确认订单分批议价，避免一次固定全部远期材料价格。','价格弹性'],
['先落实关键交付','提前安排替代难、交期长的零部件排产，价格通过后续计价窗口确认。','交付保障'],
['等供需信号再提高覆盖','持续观察同口径库存与加工需求，趋势明确后再调整锁价范围。','节奏调整']];
$('strategy-period').textContent='参考月份 '+month+' · 下游零部件与整机采购';
$('strategy-cards').innerHTML=cards.map((c,i)=>'<article><div class="strategy-top"><span class="strategy-number">0'+(i+1)+'</span><span class="badge">'+c[2]+'</span></div><h3>'+c[0]+'</h3><p>'+c[1]+'</p></article>').join('');
$('modules').hidden=true; $('module-cards').replaceChildren();


}

function reportFor(month){
const local=analysisData?.months?.[month];if(local)return {...local.marketView,sourceList:local.marketView.sourceKeys.map(k=>local.sources[k])};
const historical=contextData?.historicalReports?.find(r=>r.month===month);if(historical)return {...historical,inherited:true,sourceList:[{title:historical.titleZh,url:historical.url,published:historical.published}]};
const ids={june:'2025-06',july:'2025-07',aug1:'2025-08',aug2:'2025-08',aug3:'2025-08',sep1:'2025-09',sep3:'2025-09',oct:'2025-10',nov:'2025-11',dec1:'2025-12',dec2:'2025-12',dec3:'2025-12'};
const reports=contextData?.reports?.filter(r=>ids[r.id]===month)||[];
return reports.length?{...reports.at(-1),inherited:true,sourceList:reports.map(r=>({title:r.titleZh,url:r.url,published:r.published}))}:null;
}
function sourceLink(s){return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title)+' ↗</a><small class="source-date">发布 '+esc(s.published||('未标注；核验 '+(s.retrievedAt||'2026-11-05')))+'</small>';}


function regionMap(month){const r=analysisData.regionalProduction;if(!r||month<'2026-03')return '';return '<figure class="aluminum-region-map"><figcaption>'+esc(r.title)+'<small>2025年度结构背景 · 报告约数</small></figcaption><img src="'+r.asset+'" alt="中国地图：山东约16%，内蒙古15%，新疆15%，云南14%，甘肃7%，青海7%，广西6%"><ul>'+r.shares.map(v=>'<li><span>'+esc(v.name)+'</span><b>约'+v.share+'%</b></li>').join('')+'</ul>'+sourceLink(r.source)+'<p class="map-method">年度产地结构，不代表所选月占比；内蒙古占比覆盖全区，电价卡仅为蒙西。地图为产区定位示意。</p></figure>';}

function moduleContext(id,month){
if(id==='supply'){const p=analysisData.policyContext;return '<aside class="policy-context"><span class="badge">产能政策背景</span><h4>'+esc(p.title)+'</h4><p>'+esc(p.explanation)+'</p>'+sourceLink({title:'工信部 · 总量约束与置换政策',url:p.policyUrl,published:p.policyDate})+(month>='2026-08'?'<p>'+esc(p.currentText)+'</p>'+sourceLink({title:'焦作万方 · 2026半年报，第9页',url:p.currentUrl,published:p.currentDate}):'<p>本月运行产能见下方已收录数据；缺值时不沿用后续月份填充。</p>')+'</aside>';}
if(id==='demand'){const d=analysisData.demandStructure;let angle=0;const slices=d.sectors.map(s=>{const from=angle;angle+=s.share*3.6;return s.color+' '+from+'deg '+angle+'deg';}).join(',');return '<figure class="demand-structure"><figcaption>'+esc(d.title)+' <span class="badge">'+esc(d.scope)+'</span></figcaption><div class="donut-layout"><div class="demand-donut" role="img" aria-label="'+esc(d.sectors.map(s=>s.name+' '+s.share+'%').join('，'))+'" style="background:conic-gradient('+slices+')"><div><strong>'+d.year+'</strong><span>年度消费结构</span></div></div><ul class="donut-legend">'+d.sectors.map(s=>'<li><i style="background:'+s.color+'"></i><span>'+esc(s.name)+'</span><b>'+s.share.toFixed(1)+'%</b></li>').join('')+'</ul></div><p>'+esc(d.note)+'</p>'+sourceLink(d.source)+'<h4 class="monthly-sector-label">'+month+' · 对应行业景气与库存</h4></figure>';}
if(id==='inputs'){const p=analysisData.regionalPower,d=p.months[month];return '<aside class="regional-power">'+regionMap(month)+'<h4>重点铝产区电价</h4><small>'+esc(p.scope)+' · '+esc(p.unit)+'</small>'+(d?'<p class="power-summary">'+esc(d.summary)+'</p><div class="power-region-grid">'+d.regions.map(v=>'<div><b>'+esc(v.region)+'</b><strong>'+v.value.toFixed(4)+'</strong><span>'+esc(v.definition)+'</span><em>'+(v.previous?'环比 '+pct((v.value/v.previous-1)*100):'环比 —')+'</em>'+sourceLink({title:'公告存档 ↗',url:v.url,published:v.published})+'</div>').join('')+'</div>'+(d.impact?'<p class="power-impact">'+esc(d.impact)+'</p>':''):'<p class="power-summary">本月重点产区电价尚未收录，不沿用其他月份判断涨跌。</p>')+'<small class="power-footnote">'+esc(p.note)+'</small></aside>';}

return '';}


function macroComparison(v,a){const c=v.comparison,signed=n=>(n>0?'+':'')+fmt(n);return '<div class="macro-comparisons"><span>同比 <b>'+(Number.isFinite(c?.yoy)?signed(c.yoy)+' '+esc(c.unit):'—')+'</b></span><span>环比 <b>'+(Number.isFinite(c?.mom)?signed(c.mom)+' '+esc(c.unit):'—')+'</b></span></div>'+(v.impact?'<p class="macro-impact">'+esc(v.impact)+'</p>':'')+(c?.source&&a.sources[c.source]?'<div class="comparison-source">'+sourceLink(a.sources[c.source])+'</div>':'')+(c?.missing?'<small>'+esc(c.missing)+'</small>':'');}

function renderAnalysis(month,row){
const a=analysisData?.months?.[month],r=reportFor(month);
if(a){
const filled=a.coverage.filter(c=>c.status==='recorded').length;
$('analysis-content').innerHTML='<div class="monthly-conclusion"><p class="eyebrow">MONTHLY ASSESSMENT / '+month+'</p><h3>'+esc(a.marketView.titleZh)+'</h3><p class="conclusion-lead">'+esc(a.summary)+'</p><div class="support-grid">'+a.drivers.map(d=>'<div><b>'+esc(d.label)+'</b><p>'+esc(d.text)+'</p>'+sourceLink(a.sources[d.source])+'</div>').join('')+'</div><div class="duration-grid"><div><span class="badge">短期 · 1—3个月</span><p>'+esc(a.duration.near)+'</p></div>'+(a.duration.medium?'<div><span class="badge">中期 · 3—6个月</span><p>'+esc(a.duration.medium)+'</p></div>':'')+'<div><span class="badge">长期 · 6—12个月</span><p>'+esc(a.duration.far)+'</p></div></div><p class="duration-verdict"><strong>'+esc(a.duration.headline)+'</strong></p><p class="analysis-timing">月度复盘，部分资料事后发布；锁价需考虑价格回落与订单变更风险。</p></div>';
const stateLabels={recorded:'已录入月值',qualitative:'仅有定性背景',private_input:'需企业账单',partial_access:'部分公开，逐月待补',method_unverified:'累计区间待核实',collection_pending:'采集未完成',technical_pending:'技术取数待处理',download_unverified:'文件访问待核实'};
$('framework-cards').innerHTML=a.modules.map((m,i)=>{
const coverage=a.coverage.filter(c=>c.group===m.id),count=coverage.filter(c=>c.status==='recorded').length;
const positive=m.id==='supply'?'核对当月产量与运行产能，区分增量、存量和政策限制。':m.id==='demand'?'重点行业各看一个月度景气指标，再用加工开工与库存交叉验证。':m.id==='inputs'?'氧化铝、电价与其他投入共同决定成本，模型值与企业账单分开。':'将实际铝贸易与宏观景气分开，核对内外市场是否同向。';
const counter=m.id==='supply'?'产能上限不等于当月减产；海外扰动不能直接替代国内供给证据。':m.id==='demand'?'终端产量不是铝耗；汽车、光伏、电网等不可互相替代，单点去库也不是全月消费。':m.id==='inputs'?'原料降价可能削弱成本推动逻辑；省级代理购电价格也不等于铝厂实际结算价。':'制造业PMI不是铝专用需求，原铝贸易也不能代替铝材出口。';
return '<article class="framework-card framework-'+m.id+'"><div class="framework-title"><span class="eyebrow">0'+(i+1)+'</span><h3>'+esc(m.title)+'</h3></div>'+moduleContext(m.id,month)+'<div class="framework-metrics">'+(m.metrics.length?m.metrics.map(v=>'<div data-al-metric="'+esc(v.id)+'"><span>'+esc(v.label)+' <small class="metric-type">'+(v.evidenceType==='proxy'?'背景／需求代理':v.method==='derived_difference'?'计算值':'直接指标／模型')+'</small></span><strong>'+fmt(v.value)+' <small>'+esc(v.unit)+'</small></strong><span class="metric-change">'+esc(v.change)+'</span>'+(m.id==='macro'?macroComparison(v,a):'')+'<div class="metric-source">'+sourceLink(a.sources[v.source])+'</div>'+(v.caveat?'<small class="metric-caveat">'+esc(v.caveat)+'</small>':'')+'</div>').join(''):(m.id==='inputs'&&analysisData.regionalPower.months[month]?'':'<p class="no-monthly-values">本月尚无核验数值；保留已找到的观点与待验证项。</p>'))+'</div>'+(m.id==='supply'?'<p class="module-monthly-insight">'+esc(m.text)+'</p>':'')+'<div class="framework-source"><small>板块观点来源</small>'+sourceLink(a.sources[m.source])+'</div><details class="core-coverage"><summary>完整指标清单与缺口 · '+coverage.length+' 组</summary>'+coverage.map(c=>'<div class="core-row"><strong>'+esc(c.label)+'</strong><span class="badge '+(c.status==='recorded'?'':'partial')+'">'+stateLabels[c.status]+'</span><p>'+esc(c.reason)+'</p></div>').join('')+'</details></article>';
}).join('');
}else{
$('analysis-content').innerHTML='<div class="monthly-conclusion"><p class="eyebrow">MONTHLY ASSESSMENT / '+month+'</p><h3>'+(r?'当月市场观点与分析框架':'当月分析证据尚未齐全')+'</h3><p>'+(r?esc(r.summaryZh):'当前仅有价格记录，不能据价格涨跌反推供需原因。')+'</p>'+(r?'<div>'+r.sourceList.map(sourceLink).join('')+'</div><p class="analysis-timing">原项目历史观点缓存 · '+esc(r.coverageZh||'阶段背景')+' · 发布 '+esc(r.published)+'</p>':'')+'<div class="duration-verdict">短期与中长期持续性：当月证据不足，暂不作方向判断。</div></div>';
$('framework-cards').innerHTML=['供给与政策','需求与库存','原料与能源','宏观与国际贸易'].map(g=>'<article class="framework-card framework-pending"><h3>'+g+'</h3><small>该历史月尚未形成经核验的板块指标组合。</small></article>').join('');
}
$('year-views').innerHTML='<div class="year-views-label"><strong>2026 月度市场观点</strong><small>已结束月份 · 11月进行中，不补造整月结论</small></div><div class="year-buttons">'+Object.keys(analysisData.months).filter(m=>m.startsWith('2026')).sort().map(m=>'<button type="button" data-review-month="'+m+'" aria-pressed="'+(m===month)+'">'+Number(m.slice(5))+'月</button>').join('')+'</div>';
document.querySelectorAll('[data-review-month]').forEach(b=>b.addEventListener('click',()=>{$('month').value=b.dataset.reviewMonth;render();}));
}


let popTimer,pointPinned=false,popMonth=null,popAnchor=null;
function hideMarketView(){clearTimeout(popTimer);$('market-popover').hidden=true;pointPinned=false;document.querySelectorAll('#chart [aria-expanded]').forEach(e=>e.setAttribute('aria-expanded','false'));}
function showMarketView(month,anchor,pinned=false){
clearTimeout(popTimer);pointPinned=pinned;popMonth=month;popAnchor=anchor;
const row=rows.find(r=>r.month===month),r=reportFor(month),box=$('market-popover');
$('popover-content').innerHTML='<p class="eyebrow">'+esc(month)+' / MARKET VIEW</p><h3>A00铝锭 · '+fmt(row?.price)+' 元/吨</h3><p class="popover-label">市场观点</p><p>'+(r?esc(r.summaryZh):'该月暂无已收录的市场观点；价格记录不等于市场归因。')+'</p>'+(r?'<small>'+esc(r.coverageZh||'月度背景')+(r.inherited?' · 原项目历史缓存':' · 多源复盘')+'</small><div class="popover-sources">'+r.sourceList.map(sourceLink).join('')+'</div><p class="popover-timing">'+(r.published>(row?.date||month+'-31')?'事后回顾：发布于观察期之后。':'阶段观点：不代表整月行情的全部原因。')+'</p>':'')+'<p class="popover-hint">点击图点或按 Enter 可切换本月分析；Esc 关闭。</p>';
box.hidden=false;document.querySelectorAll('#chart [aria-expanded]').forEach(e=>e.setAttribute('aria-expanded',String(e===anchor)));
const b=anchor.getBoundingClientRect(),shell=document.querySelector('.shared-shell').getBoundingClientRect(),w=Math.min(370,innerWidth-24);
box.style.width=w+'px';box.style.maxHeight=Math.max(150,Math.min(innerWidth<550?250:420,innerHeight-shell.bottom-26))+'px';
const height=box.getBoundingClientRect().height;let left=b.left>innerWidth/2?b.left-w-20:b.right+20;left=Math.max(12,Math.min(innerWidth-w-12,left));let top=b.bottom+16;if(top+height>innerHeight-12)top=b.top-height-16;if(top<shell.bottom+10)top=Math.max(shell.bottom+10,Math.min(innerHeight-height-12,b.top-20));
box.style.left=left+'px';box.style.top=top+'px';
}
function attachChartViews(){
document.querySelectorAll('#chart [data-month]').forEach((dot,i,list)=>{
dot.addEventListener('pointerenter',()=>showMarketView(dot.dataset.month,dot));
dot.addEventListener('focus',()=>showMarketView(dot.dataset.month,dot));
dot.addEventListener('pointerleave',()=>{if(!pointPinned)popTimer=setTimeout(hideMarketView,240);});
dot.addEventListener('click',()=>{const m=dot.dataset.month;$('month').value=m;render();const fresh=document.querySelector('#chart [data-month="'+m+'"]');if(fresh)showMarketView(m,fresh,true);});
dot.addEventListener('keydown',e=>{if(e.key==='Escape'){hideMarketView();dot.blur();return;}if(e.key==='Enter'||e.key===' '){e.preventDefault();dot.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}let n;if(e.key==='ArrowRight')n=Math.min(list.length-1,i+1);if(e.key==='ArrowLeft')n=Math.max(0,i-1);if(e.key==='Home')n=0;if(e.key==='End')n=list.length-1;if(n!==undefined){e.preventDefault();list[n].focus();}});
});
}
$('popover-close').addEventListener('click',hideMarketView);
$('market-popover').addEventListener('pointerenter',()=>clearTimeout(popTimer));
$('market-popover').addEventListener('pointerleave',()=>{if(!pointPinned)popTimer=setTimeout(hideMarketView,240);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')hideMarketView();});
window.addEventListener('resize',hideMarketView);window.addEventListener('scroll',()=>{if(!$('market-popover').hidden&&popAnchor?.isConnected){const b=popAnchor.getBoundingClientRect(),shell=document.querySelector('.shared-shell').getBoundingClientRect();if(b.bottom>shell.bottom&&b.top<innerHeight)showMarketView(popMonth,popAnchor,pointPinned);else hideMarketView();}},{passive:true});


function chart(month){
hideMarketView();
const start=$('range').value==='all'?'2024-01':previous(month,11),all=[];
for(let m=start;m<=month;m=previous(m,-1))all.push(m);
const values=rows.filter(r=>r.month>=start&&r.month<=month),svg=$('chart');
if(!values.length){svg.innerHTML='<text x="25" y="90" fill="#718293">所选区间无完整月度价格</text>';$('chart-table').innerHTML='';return;}
const min=Math.min(...values.map(r=>r.price))-500,max=Math.max(...values.map(r=>r.price))+500,x=m=>65+all.indexOf(m)*860/Math.max(all.length-1,1),y=v=>190-(v-min)/(max-min)*160;
let h='';for(let i=0;i<4;i++){const v=min+(max-min)*i/3;h+='<line x1="65" x2="930" y1="'+y(v)+'" y2="'+y(v)+'" stroke="#dce5eb"/><text x="4" y="'+(y(v)+4)+'" fill="#718293" font-size="11">'+fmt(v)+'</text>';}
let prev=null;for(const m of all){const r=rows.find(r=>r.month===m);if(!r){prev=null;continue;}if(prev)h+='<line x1="'+x(prev.month)+'" y1="'+y(prev.price)+'" x2="'+x(m)+'" y2="'+y(r.price)+'" stroke="#1d5e86" stroke-width="2.5"/>';h+='<circle data-month="'+m+'" tabindex="0" role="button" aria-label="'+m+' A00铝锭 '+fmt(r.price)+'元每吨，查看市场观点" aria-controls="market-popover" aria-expanded="false" cx="'+x(m)+'" cy="'+y(r.price)+'" r="4" fill="#1d5e86"><title>'+m+'：'+fmt(r.price)+'元/吨；'+esc(r.period)+'</title></circle>';prev=r;}
for(const m of [all[0],all[Math.floor(all.length/2)],all.at(-1)])h+='<text x="'+x(m)+'" y="225" text-anchor="middle" fill="#718293" font-size="11">'+m+'</text>';
svg.innerHTML=h;attachChartViews();
$('chart-table').innerHTML='<details><summary>查看可访问的月度数据表（含缺值）</summary><table><tr><th>月份</th><th>元/吨</th><th>状态</th></tr>'+all.map(m=>{const r=rows.find(r=>r.month===m);return '<tr><td>'+m+'</td><td>'+fmt(r?.price)+'</td><td>'+(r?'原项目缓存 · 下旬代理':'缺值')+'</td></tr>';}).join('')+'</table></details>';
}
function sources(){const filter=$('access-filter').value,q=$('search').value.trim().toLowerCase(),items=ledger.indicators.filter(r=>(filter==='all'||r.access===filter)&&JSON.stringify(r).toLowerCase().includes(q));
$('source-count').textContent=items.length+' / '+ledger.indicators.length+' 项指标';
$('source-table').innerHTML='<table><thead><tr><th>指标 / 模块</th><th>访问状态 / 接入</th><th>月度方法</th><th>历史与采集方式</th><th>限制 / 核验日</th></tr></thead><tbody>'+items.map(r=>'<tr><td><strong>'+esc(r.name)+'</strong><small>'+esc(r.module)+' · '+esc(r.unit)+'</small><a target="_blank" rel="noopener" href="'+esc(r.url)+'">来源原文 ↗</a></td><td><span class="badge '+r.access+'">'+statusNames[r.access]+'</span><p>'+(r.id==='price'?'已有历史缓存':r.observations?.length?'已人工核验录入':'未连接')+'</p></td><td>'+esc(r.monthlyMethod)+'</td><td>'+esc(r.history)+'<p>'+esc(r.collection)+'</p></td><td>'+esc(r.caveats)+(r.coverageReason?'<p class="coverage-reason">'+esc(r.coverageReason)+'</p>':'')+'<small>'+r.verifiedAt+'</small></td></tr>').join('')+'</tbody></table>';
}
$('export').addEventListener('click',()=>{if(!ledger)return;const url=URL.createObjectURL(new Blob([JSON.stringify(ledger,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='aluminum-monthly-source-register.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('month').addEventListener('change',()=>{if(/^\d{4}-\d{2}$/.test($('month').value))render();});$('range').addEventListener('change',render);$('access-filter').addEventListener('change',sources);$('search').addEventListener('input',sources);

const categories={aluminum:['铝','ALUMINUM','Al'],copper:['铜','COPPER','Cu'],iron:['铁（钢材）','STEEL','Fe']};
const tabs=[...document.querySelectorAll('[data-category][role="tab"]')];
function switchCategory(key,updateUrl=true){
hideMarketView();
key=({steel:'iron',memory:'wafer'})[key]||key;if(!categories[key]){key='aluminum';updateUrl=true;}document.body.dataset.category=key;
for(const tab of tabs){const active=tab.dataset.category===key;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;}
$('aluminum-page').hidden=key!=='aluminum';$('category-empty').hidden=key==='aluminum';$('category-empty').setAttribute('aria-labelledby','tab-'+key);
document.dispatchEvent(new CustomEvent('material-category',{detail:key}));
if(key==='aluminum'&&ledger)render();

if(updateUrl){const u=new URL(location.href);u.searchParams.set('category',key);u.hash='';history.replaceState({},'',u);}}
tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>switchCategory(tab.dataset.category));tab.addEventListener('keydown',e=>{let n;if(e.key==='ArrowRight')n=(index+1)%tabs.length;if(e.key==='ArrowLeft')n=(index+tabs.length-1)%tabs.length;if(e.key==='Home')n=0;if(e.key==='End')n=tabs.length-1;if(n!==undefined){e.preventDefault();tabs[n].focus();switchCategory(tabs[n].dataset.category);}});});
document.querySelectorAll('header nav a')[3].addEventListener('click',()=>{if(document.body.dataset.category==='aluminum')$('sources').open=true;else document.getElementById('material-sources')?.setAttribute('open','');});
switchCategory(new URLSearchParams(location.search).get('category')||'aluminum',false);


Promise.all(['./data/monthly-sources.json','./data/monthly-observations.json','./data/monthly-analysis.json','./data/aluminum-context.json'].map(async u=>{const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw Error('数据文件读取失败');return r.json();})).then(([l,h,a,c])=>{ledger=l;analysisData=a;contextData=c;rows=h.observations.filter(r=>['inherited_cache','verified'].includes(r.status)&&Number.isFinite(r.value)).map(r=>({month:r.month,price:r.value,source:r.sourceUrl,date:r.observedAt,period:r.month+'-21/'+r.observedAt})).sort((a,b)=>a.month.localeCompare(b.month));$('month').value=analysisData.defaultMonth||rows.at(-1)?.month||'2026-10';render();sources();}).catch(e=>{$('error').textContent=e.message+'；未生成市场建议。';});
})();






