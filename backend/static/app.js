async function fetchJSON(url){const r=await fetch(url);if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}
function setSummary(data){
  document.getElementById('totalIndicators').textContent=data.totals.indicators;
  document.getElementById('withData').textContent=data.totals.indicators_with_data;
  document.getElementById('totalPoints').textContent=data.totals.economic_data_points;
  document.getElementById('generatedAt').textContent=data.generated_at;
  const tbody=document.getElementById('sourceRows');tbody.innerHTML='';
  const sf=document.getElementById('sourceFilter');sf.innerHTML='<option value="">همه</option>';
  for(const s of data.sources){
    const tr=document.createElement('tr');tr.innerHTML=`<td>${s.source}</td><td>${s.indicators}</td><td>${s.indicators_with_data}</td>`;tbody.appendChild(tr);
    const o=document.createElement('option');o.value=s.source;o.textContent=s.source;sf.appendChild(o);
  }
}
function setSymbols(rows){
  const tbody=document.getElementById('symbolRows');tbody.innerHTML='';
  for(const r of rows){
    const badge=r.has_data?'<span class="badge ok">قابل نمایش</span>':'<span class="badge no">فقط کشف شده</span>';
    const tr=document.createElement('tr');tr.innerHTML=`<td>${r.symbol}</td><td>${r.name}</td><td>${r.source}</td><td>${r.frequency||'-'}</td><td>${r.data_points_count}</td><td>${badge}</td>`;tbody.appendChild(tr);
  }
}
async function loadAll(){
  const source=document.getElementById('sourceFilter').value;
  const withDataOnly=document.getElementById('withDataOnly').checked;
  const summary=await fetchJSON('/api/data/summary');setSummary(summary);
  const p=new URLSearchParams({limit:'400'});if(source)p.set('source',source);if(withDataOnly)p.set('with_data_only','true');
  const symbols=await fetchJSON(`/api/data/symbols/available?${p.toString()}`);setSymbols(symbols);
}
document.getElementById('reloadBtn').addEventListener('click',()=>loadAll().catch(e=>alert(e.message)));
loadAll().catch(e=>alert('خطا در بارگذاری داشبورد: '+e.message));
