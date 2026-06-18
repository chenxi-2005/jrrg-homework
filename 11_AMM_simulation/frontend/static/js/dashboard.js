/**
 * Dashboard — ECharts 价格柱状图 + 储备曲线
 */
var _priceChart = null, _curveChart = null;

function initChart(domId) {
    var el = document.getElementById(domId); if (!el) return null;
    var c = echarts.init(el); c.setOption({}); return c;
}

async function loadCharts() {
    try {
        var r = await fetch('/api/state'); var st = await r.json(); var ids = Object.keys(st.pools);
        if (!ids.length) return;

        // --- Price bar chart ---
        var steps = [], prices = [];
        for (var i = 0; i < ids.length; i++) {
            var pr = await fetch('/api/session/price-history/' + ids[i]); var d = await pr.json();
            if (d.history) { for (var j = 0; j < d.history.length; j++) { steps.push(String(d.history[j].step)); prices.push(d.history[j].spot_price); } }
        }
        if (!_priceChart) _priceChart = initChart('chart-price');
        if (_priceChart) {
            _priceChart.setOption({
                tooltip: {trigger:'axis'},
                grid: {left:55,right:15,top:15,bottom:35},
                xAxis: {type:'category', data:steps, axisLabel:{fontSize:10}},
                yAxis: {type:'value', axisLabel:{fontSize:10}, splitLine:{lineStyle:{color:'#eee'}}},
                series: [{type:'bar', data:prices,
                    itemStyle:{color:function(p){return p.dataIndex>0&&p.value>=prices[p.dataIndex-1]?'#00cc96':'#ef553b';}}}],
            });
        }

        // --- Reserve curve ---
        var pid0 = ids[0], p0 = st.pools[pid0];
        var cr = await fetch('/api/pools/' + pid0 + '/reserve-curve'); var cd = await cr.json();
        var curveData = []; for (var k = 0; k < cd.curve.length; k++) { curveData.push([cd.curve[k].reserve_a, cd.curve[k].reserve_b]); }
        if (!_curveChart) _curveChart = initChart('chart-curve');
        if (_curveChart) {
            _curveChart.setOption({
                tooltip: {trigger:'item', formatter:function(p){return p0.token_a+': '+p.value[0].toFixed(1)+'<br/>'+p0.token_b+': '+p.value[1].toFixed(1);}},
                grid: {left:60,right:15,top:30,bottom:40},
                xAxis: {type:'value', name:p0.token_a+' 储备', nameLocation:'center', nameGap:25, axisLabel:{fontSize:10}, splitLine:{lineStyle:{color:'#eee'}}},
                yAxis: {type:'value', name:p0.token_b+' 储备', nameLocation:'center', nameGap:40, axisLabel:{fontSize:10}, splitLine:{lineStyle:{color:'#eee'}}},
                series: [
                    {type:'line', data:curveData, showSymbol:false, lineStyle:{color:'#636efa',width:2}, name:'x*y=k'},
                    {type:'scatter', data:[[cd.current.reserve_a, cd.current.reserve_b]], symbolSize:14,
                        itemStyle:{color:'#ef553b'}, label:{show:true,position:'right',formatter:'当前',fontSize:12,color:'#ef553b'}, name:'当前'},
                ],
            });
        }
    } catch(e) { console.error(e); }
}

// Pool cards, summary (unchanged)
async function refreshAll() { await loadCards(); await loadSummary(); await loadCharts(); }
async function loadCards() {
    try { var r=await fetch('/api/pools');var d=await r.json();var pools=d.pools;var c=document.getElementById('pool-cards');if(!c)return;if(!Object.keys(pools).length){c.innerHTML='<div class="col-12 text-center text-muted">暂无流动性池</div>';return;}var h='';for(var pid in pools){var p=pools[pid];var rA=parseFloat(p.reserve_a).toLocaleString(undefined,{maximumFractionDigits:2});var rB=parseFloat(p.reserve_b).toLocaleString(undefined,{maximumFractionDigits:2});var price=parseFloat(p.spot_price).toLocaleString(undefined,{maximumFractionDigits:2});h+='<div class="col-md-6 col-lg-4"><div class="card pool-card" onclick="location.href=\'/pools/'+pid+'\'" role="button"><div class="card-body"><h6 class="card-title">'+p.token_a+'/'+p.token_b+'</h6><div class="row text-center mb-2"><div class="col-6"><small class="text-muted">'+p.token_a+' 储备</small><br><strong>'+rA+'</strong></div><div class="col-6"><small class="text-muted">'+p.token_b+' 储备</small><br><strong>'+rB+'</strong></div></div><hr class="my-1"><div class="row text-center small"><div class="col-4"><span class="text-muted">价格</span><br>'+price+'</div><div class="col-4"><span class="text-muted">交易数</span><br>'+p.swap_count+'</div><div class="col-4"><span class="text-muted">手续费</span><br>'+(parseFloat(p.fee_rate)*100).toFixed(1)+'%</div></div></div></div></div>';}c.innerHTML=h;}catch(e){}
}
async function loadSummary() {
    try { var r=await fetch('/api/summary');var s=await r.json();var el=document.getElementById('summary-stats');if(!el)return;el.innerHTML='<div class="col-md-3"><small class="text-muted">当前步数</small><br><strong>'+s.step+'/'+s.max_steps+'</strong></div><div class="col-md-3"><small class="text-muted">池数量</small><br><strong>'+s.pools+'</strong></div><div class="col-md-3"><small class="text-muted">用户数</small><br><strong>'+s.users+'</strong></div><div class="col-md-3"><small class="text-muted">事件总数</small><br><strong>'+s.total_events+'</strong></div>';}catch(e){}
}

refreshAll(); setInterval(refreshAll, 3000);
