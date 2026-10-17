const clusters = [
  {id:'CL-2048',title:'Authentication timeouts',count:142,time:'09:14',confidence:94,status:'Needs review',systems:['Auth Gateway','Identity API','Session Store'],icon:'⌁',causes:[['Certificate rotation missed on auth-gw-03',94,'Change CHG-8821 applied to the authentication gateway 40 minutes before the first ticket.'],['Identity provider connection pool exhausted',76,'Affected services share the same identity API dependency.'],['Session store latency after config update',51,'A related configuration update overlaps the incident onset.']]},
  {id:'CL-2046',title:'Payment queue delays',count:86,time:'08:42',confidence:88,status:'Needs review',systems:['Payment API','Message Broker','Ledger'],icon:'⇄',causes:[['Broker partition rebalance',88,'Broker maintenance ended 18 minutes before queue depth began rising.'],['Ledger write contention',71,'Payment and ledger retries rose together across 3 systems.'],['Connection limit reached on payment API',43,'A service limit change may explain the gradual onset.']]},
  {id:'CL-2041',title:'Report generation failures',count:53,time:'07:26',confidence:82,status:'Proposed',systems:['Reporting Service','Warehouse'],icon:'▤',causes:[['Warehouse query plan regression',82,'A query index change preceded the first failed report by 26 minutes.'],['Reporting worker memory pressure',65,'Worker restarts overlap the failures and affect long reports most.'],['Upstream export delay',39,'Warehouse exports are a shared dependency for affected reports.']]},
  {id:'CL-2039',title:'VPN reconnect loop',count:38,time:'06:51',confidence:76,status:'Needs review',systems:['Remote Access','Device Registry'],icon:'⌁',causes:[['Remote access policy mismatch',76,'Policy rollout targeted the affected gateway group this morning.'],['Device registry lookup latency',61,'Reconnect attempts correlate with elevated registry response time.'],['Expired edge certificate',32,'No matching change found; certificate age warrants inspection.']]},
  {id:'CL-2033',title:'Inventory sync lag',count:24,time:'05:18',confidence:71,status:'Proposed',systems:['Inventory API','Event Bus'],icon:'⟳',causes:[['Event consumer fell behind',71,'Consumer lag increased 11 minutes before reports of stale inventory.'],['Schema mismatch in sync payload',58,'The affected events share a newer payload version.'],['Inventory database lock contention',36,'Write latency rose on the shared inventory store.']]},
  {id:'CL-2029',title:'Search index unavailable',count:19,time:'03:47',confidence:65,status:'Needs review',systems:['Search Service','Catalog API'],icon:'⌕',causes:[['Index shard allocation failure',65,'Search nodes report unassigned shards during the incident window.'],['Catalog backfill saturation',53,'A catalog backfill overlaps the increase in search timeouts.'],['Storage capacity threshold reached',28,'Disk usage crossed its warning level on one search node.']]},
];

const $ = (selector) => document.querySelector(selector);
const rows = $('#cluster-rows');
const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let selectedId = clusters[0].id;
let sortDescending = true;

function renderRows() {
  const query = $('#search-input').value.trim().toLowerCase();
  const status = $('#status-filter').value;
  let filtered = clusters.filter((item) => {
    const matchesQuery = !query || `${item.id} ${item.title} ${item.systems.join(' ')}`.toLowerCase().includes(query);
    const matchesStatus = status === 'all' || (status === 'review' ? item.status === 'Needs review' : item.status === 'Proposed');
    return matchesQuery && matchesStatus;
  });
  filtered = filtered.slice().sort((a,b) => sortDescending ? b.count-a.count : a.count-b.count);
  $('#visible-count').textContent = String(filtered.length);
  $('#empty-state').hidden = filtered.length > 0;
  rows.innerHTML = filtered.map((item) => `<tr data-id="${esc(item.id)}" class="${item.id === selectedId ? 'selected' : ''}" tabindex="0" aria-label="Open ${esc(item.title)}">
    <td><div class="cluster-title-cell"><span class="cluster-symbol">${esc(item.icon)}</span><span><span class="cluster-main">${esc(item.title)}</span><span class="cluster-id">${esc(item.id)}</span></span></div></td>
    <td><span class="incident-number">${item.count}</span><span class="incident-caption">incidents</span></td>
    <td>${esc(item.time)} <span class="incident-caption">today</span></td>
    <td><span class="confidence">${item.confidence}% <span class="confidence-bar"><i style="width:${item.confidence}%"></i></span></span></td>
    <td><span class="status-pill ${item.status === 'Proposed' ? 'status-proposed' : 'status-review'}">${esc(item.status)}</span></td><td><span class="row-arrow">›</span></td>
  </tr>`).join('');
}

function renderDetail(id) {
  const item = clusters.find((cluster) => cluster.id === id);
  if (!item) return;
  selectedId = id;
  $('#detail-id').textContent = `CLUSTER ${item.id}`;
  $('#detail-title').textContent = item.title;
  $('#detail-state').textContent = item.status.toUpperCase();
  $('#detail-time').textContent = `First seen ${item.time} today`;
  $('#detail-count').textContent = `${item.count} incidents`;
  $('#detail-systems').innerHTML = item.systems.slice(0,2).map((system) => `<span class="system-tag">${esc(system)}</span>`).join('') + (item.systems.length > 2 ? `<span class="system-tag muted-tag">+${item.systems.length-2}</span>` : '');
  $('#cause-list').innerHTML = item.causes.map((cause,index) => `<article class="cause-card"><div class="cause-top"><span class="rank-badge">${index+1}</span><span class="cause-name">${esc(cause[0])}</span><span class="cause-score">${cause[1]}%</span></div><p class="cause-reason">${esc(cause[2])}</p></article>`).join('');
  $('#propose-button').innerHTML = item.status === 'Proposed' ? '<span>✓</span> Proposal saved' : '<span>＋</span> Propose problem';
  renderRows();
}

function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 2600);
}

rows.addEventListener('click', (event) => {
  const row = event.target.closest('tr[data-id]');
  if (row) renderDetail(row.dataset.id);
});
rows.addEventListener('keydown', (event) => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('tr[data-id]')) {
    event.preventDefault();
    renderDetail(event.target.dataset.id);
  }
});
$('#search-input').addEventListener('input', renderRows);
$('#status-filter').addEventListener('change', renderRows);
$('#sort-button').addEventListener('click', () => { sortDescending = !sortDescending; renderRows(); toast(`Sorted by incident count: ${sortDescending ? 'highest first' : 'lowest first'}`); });
$('#propose-button').addEventListener('click', () => {
  const item = clusters.find((cluster) => cluster.id === selectedId);
  if (item.status === 'Proposed') { toast('This proposal is already saved in the demo.'); return; }
  item.status = 'Proposed';
  renderDetail(selectedId);
  toast(`Problem proposal saved for ${item.id}. Human review required.`);
});
$('#refresh-button').addEventListener('click', (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  button.querySelector('.button-icon').textContent = '…';
  setTimeout(() => { button.disabled = false; button.querySelector('.button-icon').textContent = '↻'; toast('Demo analysis refreshed. No live data source is connected.'); }, 700);
});
$('#export-button').addEventListener('click', () => {
  const csv = ['cluster_id,title,incident_count,first_seen,confidence,status', ...clusters.map((item) => [item.id,`"${item.title.replaceAll('"','""')}"`,item.count,item.time,item.confidence,item.status].join(','))].join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'}));
  link.download = 'incidentlens-clusters-demo.csv';
  link.click();
  URL.revokeObjectURL(link.href);
  toast('Cluster view exported as CSV.');
});
$('#view-all').addEventListener('click', () => toast('Showing the six available sample clusters.'));
document.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); $('#search-input').focus(); }
  if (event.key === 'Escape') { $('#search-input').value = ''; renderRows(); $('#search-input').blur(); }
});

renderDetail(selectedId);
