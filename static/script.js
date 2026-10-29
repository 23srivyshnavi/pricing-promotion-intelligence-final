async function refreshMetrics(){
  try{const r=await fetch('/api/metrics');if(!r.ok)throw new Error('Database tables not ready');const d=await r.json();document.querySelector('#product-count').textContent=d.products.toLocaleString();document.querySelector('#promotion-count').textContent=d.promotions.toLocaleString();const decisionTotal=d.decisions_by_status.reduce((sum,x)=>sum+Number(x.total),0);document.querySelector('#decision-count').textContent=decisionTotal.toLocaleString();document.querySelector('#decision-summary').textContent=d.decisions_by_status.map(x=>`${x.decision_status}: ${x.total}`).join(' · ')||'No decisions';document.querySelector('#db-status').textContent='Connected';}
  catch(e){document.querySelector('#db-status').textContent='Not connected';}
}
async function loadProducts(search=''){
  const body=document.querySelector('#product-rows');body.innerHTML='<tr><td colspan="6">Loading…</td></tr>';
  try{const r=await fetch('/api/products?limit=100&search='+encodeURIComponent(search));if(!r.ok)throw new Error('Could not load products');const rows=await r.json();body.innerHTML='';if(!rows.length){body.innerHTML='<tr><td colspan="6">No products found. Generate data and import it into MySQL first.</td></tr>';return;}
    rows.forEach(p=>{const tr=document.createElement('tr');[p.sku,p.name,p.category,Number(p.price_floor).toFixed(2),Number(p.price_ceiling).toFixed(2),Number(p.min_margin_pct).toFixed(1)+'%'].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.appendChild(td)});body.appendChild(tr)});
  }catch(e){body.innerHTML='<tr><td colspan="6">Database unavailable. Follow README setup instructions.</td></tr>';}
}
document.querySelector('#simulation-form').addEventListener('submit',async e=>{
  e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const ids=String(f.get('promotion_ids')||'').split(',').map(x=>x.trim()).filter(Boolean);
  const payload={};['cost','candidate_price','min_margin_pct','price_floor','price_ceiling','discount_pct','competitor_price','competitor_age_hours','stock_on_hand'].forEach(k=>{const v=f.get(k);if(v!==null&&v!=='')payload[k]=Number(v)});payload.reason=String(f.get('reason')||'');payload.promotion_ids=ids;payload.sku=String(f.get('sku')||'').trim();payload.evaluation_at=String(f.get('evaluation_at')||'2026-03-01T12:00:00');payload.stack_allowed=form.elements.stack_allowed.checked;
  const box=document.querySelector('#simulation-result');box.className='result';box.textContent='Evaluating…';
  try{const r=await fetch('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw new Error(d.error||'Simulation failed');box.className='result '+(d.decision_status==='APPROVED'?'approved':d.decision_status==='REJECTED'?'rejected':'review');box.innerHTML='';const h=document.createElement('h3');h.textContent=d.decision_status+' · '+d.reason_code;box.appendChild(h);[['Candidate price',`₹${Number(d.candidate_price).toFixed(2)}`],['Price after discount',`₹${Number(d.net_price_after_discount).toFixed(2)}`],['Margin after discount',`${Number(d.margin_pct).toFixed(2)}%`],['Explanation',d.explanation]].forEach(([k,v])=>{const p=document.createElement('p');const b=document.createElement('strong');b.textContent=k+': ';p.append(b,document.createTextNode(v));box.appendChild(p)});
  }catch(err){box.className='result rejected';box.textContent=err.message;}
});
document.querySelector('#product-search').addEventListener('submit',e=>{e.preventDefault();loadProducts(document.querySelector('#search-term').value.trim())});
refreshMetrics();loadProducts();

async function loadExceptions(){
  const body=document.querySelector('#exception-rows');body.innerHTML='<tr><td colspan="6">Loading…</td></tr>';
  try{const r=await fetch('/api/exceptions?limit=100');if(!r.ok)throw new Error('Could not load exceptions');const rows=await r.json();body.innerHTML='';if(!rows.length){body.innerHTML='<tr><td colspan="6">No rejected or review-required decisions found.</td></tr>';return;}
    rows.forEach(item=>{const tr=document.createElement('tr');[item.decision_id,item.sku,item.decision_status,item.reason_code,`₹${Number(item.candidate_price).toFixed(2)}`,item.explanation].forEach(v=>{const td=document.createElement('td');td.textContent=v??'';tr.appendChild(td)});body.appendChild(tr)});
  }catch(e){body.innerHTML='<tr><td colspan="6">Database unavailable. Generate and import data first.</td></tr>';}
}
document.querySelector('#refresh-exceptions').addEventListener('click',loadExceptions);
loadExceptions();
