/**
 * 仿真控制 — ECharts 价格走势 + 事件日志
 */
var _simChart = null;

function initChart(id){var el=document.getElementById(id);if(!el)return null;var c=echarts.init(el);c.setOption({});return c;}

async function refreshSimStatus(){try{var r=await fetch('/api/sim/status');var s=await r.json();document.getElementById('sim-step-display').textContent=s.step+' / '+s.max_steps;}catch(e){}}
async function refreshSimPools(){try{var r=await fetch('/api/pools');var d=await r.json();var h='';for(var pid in d.pools){var p=d.pools[pid];h+='<tr><td><a href="/pools/'+pid+'">'+pid+'</a></td><td>'+parseFloat(p.reserve_a).toLocaleString(undefined,{maximumFractionDigits:2})+'</td><td>'+parseFloat(p.reserve_b).toLocaleString(undefined,{maximumFractionDigits:2})+'</td><td>'+parseFloat(p.spot_price).toLocaleString(undefined,{maximumFractionDigits:2})+'</td><td>'+p.swap_count+'</td></tr>';}document.getElementById('sim-pools-body').innerHTML=h||'<tr><td colspan="5" class="text-muted">暂无池</td></tr>';}catch(e){}}
async function refreshSimEvents(){try{var r=await fetch('/api/sim/events?limit=20');var d=await r.json();var evts=d.events||[];if(!evts.length){document.getElementById('sim-events-body').innerHTML='<tr><td colspan="4" class="text-muted">暂无事件</td></tr>';return;}var tm={swap:'兑换',add_liquidity:'添加流动性',remove_liquidity:'移除流动性'};var h='';for(var i=evts.length-1;i>=0;i--){var e=evts[i];var b=e.status==='executed'?'bg-success':e.status==='failed'?'bg-danger':'bg-secondary';var tn=tm[e.event_type]||e.event_type;var sn=e.status==='executed'?'成功':e.status==='failed'?'失败':'待处理';h+='<tr><td>'+(e.scheduled_step||e.step||'-')+'</td><td><span class="badge bg-info">'+tn+'</span></td><td>'+(e.initiator||'-')+'</td><td><span class="badge '+b+'">'+sn+'</span></td></tr>';}document.getElementById('sim-events-body').innerHTML=h;}catch(e){}}
async function refreshSimChart(){try{var r=await fetch('/api/state');var st=await r.json();var ids=Object.keys(st.pools);if(!ids.length)return;var steps=[],prices=[];for(var i=0;i<ids.length;i++){var pr=await fetch('/api/pools/'+ids[i]+'/price-history');var d=await pr.json();if(d.history){for(var j=0;j<d.history.length;j++){steps.push(String(d.history[j].step));prices.push(d.history[j].spot_price);}}}if(!_simChart)_simChart=initChart('chart-sim-price');if(_simChart){_simChart.setOption({tooltip:{trigger:'axis'},grid:{left:55,right:15,top:15,bottom:35},xAxis:{type:'category',data:steps,axisLabel:{fontSize:10}},yAxis:{type:'value',axisLabel:{fontSize:10},splitLine:{lineStyle:{color:'#eee'}}},series:[{type:'bar',data:prices,itemStyle:{color:function(p){return p.dataIndex>0&&p.value>=prices[p.dataIndex-1]?'#00cc96':'#ef553b';}}}]});}}catch(e){}}
async function simAction(action){var fb=document.getElementById('sim-feedback');try{var res;var nm={run:'运行',step:'步进',reset:'重置'};switch(action){case'run':res=await fetch('/api/sim/run',{method:'POST'});break;case'step':res=await fetch('/api/sim/step?count=1',{method:'POST'});break;case'reset':res=await fetch('/api/sim/reset',{method:'POST'});break;}var d=await res.json();if(res.ok){fb.innerHTML='<div class="alert alert-success py-1">'+(nm[action]||action)+' 成功 — 步数: '+(d.current_step||d.step||d.final_step||'?')+'</div>';_simChart=null;}else{fb.innerHTML='<div class="alert alert-danger py-1">'+(d.detail||'失败')+'</div>';}refreshAll();}catch(e){fb.innerHTML='<div class="alert alert-danger py-1">错误: '+e.message+'</div>';}}
async function updateConfig(){var ms=document.getElementById('cfg-max-steps')?.value;var fb=document.getElementById('sim-feedback');try{var res=await fetch('/api/sim/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({max_steps:parseInt(ms)})});if(res.ok)fb.innerHTML='<div class="alert alert-success py-1">参数已更新</div>';}catch(e){}}
function refreshAll(){refreshSimStatus();refreshSimPools();refreshSimEvents();refreshSimChart();}

async function loadScenarios(){try{var r=await fetch('/api/sim/scenarios');var d=await r.json();var sel=document.getElementById('scenario-select');var desc=document.getElementById('scenario-desc');var m={};d.scenarios.forEach(function(s){m[s.id]=s;});sel.onchange=function(){var s=m[sel.value];if(s)desc.textContent=s.description;};var s=m[sel.value];if(s)desc.textContent=s.description;}catch(e){}}
async function loadScenario(){var n=document.getElementById('scenario-select')?.value||'default';var fb=document.getElementById('sim-feedback');try{var res=await fetch('/api/sim/load-scenario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:n})});var d=await res.json();if(res.ok){fb.innerHTML='<div class="alert alert-success py-1">已加载场景: '+d.scenario+'，步数: '+d.max_steps+'</div>';document.getElementById('cfg-max-steps').value=d.max_steps;_simChart=null;}else{fb.innerHTML='<div class="alert alert-danger py-1">加载失败</div>';}refreshAll();}catch(e){fb.innerHTML='<div class="alert alert-danger py-1">错误: '+e.message+'</div>';}}

// On first load, reset simulation so chart starts fresh
async function initSimPage() {
    await fetch('/api/sim/reset', {method:'POST'});
    await loadScenarios();
    refreshAll();
}
initSimPage();
setInterval(refreshAll, 3000);
