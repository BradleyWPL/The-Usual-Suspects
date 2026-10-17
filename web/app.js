// File: web/app.js
// History: Version 0.2, October 17, 2026
// Program: Browser-side dashboard logic for IncidentLens.
// Input: DOM selectors, dashboard endpoints, user actions, and synthetic demo fallback.
// Processing: Render summaries, clusters, incident evidence, status changes, and CSV export.
// Output: An interactive problem-review screen backed by API data.

const DEMO_CLUSTERS = [
  {id:'CL-2048',title:'Authentication timeouts',count:142,first_seen:'2026-10-12T09:14:00Z',last_seen:'2026-10-12T15:14:00Z',volume:[2,3,3,4,5,8,13,22,31,39,33,28],change_marker_percent:53,change_summary:'Gateway certificate rotation',confidence:94,status:'needs_review',systems:['Auth Gateway','Identity API','Session Store'],causes:[{candidate_cause:'Authentication gateway certificate rotation',score_percent:94,evidence:['A related change preceded the first incident.']}]},
  {id:'CL-2046',title:'Payment queue delays',count:86,first_seen:'2026-10-12T08:42:00Z',last_seen:'2026-10-12T13:45:00Z',volume:[1,2,3,5,9,15,18,16,12,10,6,3],change_marker_percent:34,change_summary:'Broker partition rebalance',confidence:88,status:'needs_review',systems:['Payment API','Message Broker','Ledger'],causes:[{candidate_cause:'Payment broker partition rebalance',score_percent:88,evidence:['A broker change overlaps the incident onset.']}]},
  {id:'CL-2041',title:'Report generation failures',count:53,first_seen:'2026-10-12T07:26:00Z',last_seen:'2026-10-12T12:26:00Z',volume:[1,2,1,4,6,9,8,11,6,4,1,1],change_marker_percent:45,change_summary:'Warehouse index update',confidence:82,status:'proposed',systems:['Reporting Service','Warehouse'],causes:[{candidate_cause:'Warehouse query plan regression',score_percent:82,evidence:['A query index change preceded the reports.']}]},
];

/** Find one dashboard element by its CSS selector. */
const $ = (selector) => document.querySelector(selector);
const rows = $('#cluster-rows');
const mobileMenuButton = $('#mobile-menu-button');
const mobileNavBackdrop = $('#mobile-nav-backdrop');
/** Escape API or user-provided text before it is inserted into the dashboard markup. */
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
/** Clamp externally supplied percentage values before using them as visible text or CSS widths. */
const safePercent = (value) => { const number = Number(value); return Number.isFinite(number) ? Math.min(100, Math.max(0, number)) : 0; };
let clusters = [];
let selectedId = null;
let sortDescending = true;
let apiAvailable = false;
let dashboardSummary = {};

/** Open or close the responsive navigation and keep its button state accessible. */
function setMobileNavOpen(open) {
  // Use the same state for visual visibility, screen-reader state, and Escape handling.
  document.querySelector('.sidebar').classList.toggle('is-open', open);
  document.body.classList.toggle('mobile-menu-open', open);
  mobileNavBackdrop.hidden = !open;
  mobileMenuButton.setAttribute('aria-expanded', String(open));
  mobileMenuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  if (open) document.querySelector('#main-navigation a')?.focus();
}

/** Convert an API status value into the short label shown in the review UI. */
function statusLabel(status) {
  return ({needs_review:'Needs review',proposed:'Proposed',approved:'Approved',dismissed:'Dismissed'})[status] || 'Needs review';
}
/** Format an ISO timestamp for the cluster detail panel. */
function formatTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',timeZone:'UTC'}).format(new Date(value));
}
/** Draw the selected cluster volume and its nearest matching change marker. */
function renderTimeline(item) {
  if (!Array.isArray(item.volume) || !item.volume.length) return;
  const max=Math.max(1,...item.volume); const step=440/Math.max(1,item.volume.length-1);
  const points=item.volume.map((value,index)=>`${(index*step).toFixed(1)} ${(98-(value/max)*82).toFixed(1)}`);
  const line=`M ${points.join(' L ')}`; const area=`${line} L 440 108 L 0 108 Z`;
  $('#volume-line').setAttribute('d',line); $('#volume-area').setAttribute('d',area);
  $('#chart-max').textContent=String(max); $('#chart-mid').textContent=String(Math.round(max/2));
  $('#chart-start').textContent=formatTime(item.first_seen); $('#chart-end').textContent=formatTime(item.last_seen);
  $('#chart-mid-time').textContent=formatTime(new Date((new Date(item.first_seen).getTime()+new Date(item.last_seen).getTime())/2));
  const marker=$('#change-marker');
  if(item.change_marker_percent!==null && item.change_marker_percent!==undefined){marker.hidden=false;marker.style.left=`${item.change_marker_percent}%`;$('#change-label').textContent=(item.change_summary||'CHANGE APPLIED').slice(0,22).toUpperCase();}
  else marker.hidden=true;
}
/** Populate the four dashboard summary counts from the API response. */
function renderSummary() {
  const number = (value) => Number(value || 0).toLocaleString();
  document.querySelectorAll('[data-summary]').forEach((node) => { node.textContent = number(dashboardSummary[node.dataset.summary]); });
  const updated = $('#analysis-updated');
  if (updated && dashboardSummary.last_analysis) updated.textContent = `Analysis generated ${new Date(dashboardSummary.last_analysis).toLocaleString()}`;
  const source = $('#source-state');
  if (source) source.textContent = apiAvailable ? 'PIPELINE CONNECTED · SIMULATED DATA' : 'SAMPLE PREVIEW · RUN THE API FOR PIPELINE DATA';
}
/** Filter, sort, and render current candidate clusters into the accessible table. */
function renderRows() {
  const query = $('#search-input').value.trim().toLowerCase();
  const status = $('#status-filter').value;
  let filtered = clusters.filter((item) => {
    const matchesQuery = !query || `${item.id} ${item.title} ${item.systems.join(' ')}`.toLowerCase().includes(query);
    const matchesStatus = status === 'all' || item.status === status;
    return matchesQuery && matchesStatus;
  });
  filtered = filtered.slice().sort((a,b) => sortDescending ? b.count-a.count : a.count-b.count);
  $('#visible-count').textContent = String(filtered.length);
  document.querySelector('.table-footer > span').innerHTML = `Showing <strong id="visible-count">${filtered.length}</strong> clusters`;
  $('#empty-state').hidden = filtered.length > 0;
  rows.innerHTML = filtered.map((item) => {
    const label = statusLabel(item.status);
    const confidence = safePercent(item.confidence);
    return `<tr data-id="${esc(item.id)}" class="${item.id === selectedId ? 'selected' : ''}" tabindex="0" aria-label="Open ${esc(item.title)}">
      <td><div class="cluster-title-cell"><span class="cluster-symbol">⌁</span><span><span class="cluster-main">${esc(item.title)}</span><span class="cluster-id">${esc(item.id)}</span></span></div></td>
      <td><span class="incident-number">${Number(item.count).toLocaleString()}</span><span class="incident-caption">incidents</span></td>
      <td>${formatTime(item.first_seen)} <span class="incident-caption">UTC</span></td>
      <td><span class="confidence">${confidence}% <progress class="confidence-bar" value="${confidence}" max="100" aria-label="Top-cause evidence score"></progress></span></td>
      <td><span class="status-pill status-${esc(item.status)}">${esc(label)}</span></td><td><span class="row-arrow">›</span></td>
    </tr>`;
  }).join('');
}
/** Render one cluster's timeline, systems, evidence ranking, and sample ticket. */
function renderDetail(id) {
  const item = clusters.find((cluster) => cluster.id === id);
  if (!item) return;
  selectedId = id;
  $('#detail-id').textContent = `CLUSTER ${item.id}`;
  $('#detail-title').textContent = item.title;
  $('#detail-state').textContent = statusLabel(item.status).toUpperCase();
  $('#detail-time').textContent = `First seen ${formatTime(item.first_seen)} UTC`;
  $('#detail-count').textContent = `${Number(item.count).toLocaleString()} incidents`;
  $('#detail-systems').innerHTML = item.systems.slice(0,2).map((system) => `<span class="system-tag">${esc(system)}</span>`).join('') + (item.systems.length > 2 ? `<span class="system-tag muted-tag">+${item.systems.length-2}</span>` : '');
  $('#cause-list').innerHTML = (item.causes || []).map((cause,index) => `<article class="cause-card"><div class="cause-top"><span class="rank-badge">${index+1}</span><span class="cause-name">${esc(cause.candidate_cause)}</span><span class="cause-score">${safePercent(cause.score_percent)}%</span></div><p class="cause-reason">${(cause.evidence || []).map(esc).join(' ')}</p></article>`).join('') || '<p class="cause-reason">No cause candidates were recorded for this cluster.</p>';
  const propose = $('#propose-button');
  propose.disabled = ['proposed','approved','dismissed'].includes(item.status);
  propose.innerHTML = item.status === 'proposed' ? '<span>✓</span> Proposal saved' : item.status === 'approved' ? '<span>✓</span> Approved' : item.status === 'dismissed' ? 'Dismissed' : '<span>＋</span> Propose problem';
  const incident = (item.incidents || [])[0];
  renderTimeline(item);
  const sample = $('#incident-sample');
  if (sample) sample.textContent = incident ? `${incident.short_description} · ${incident.incident_id}` : 'Open cluster details to inspect the incident sample.';
  renderRows();
}
/** Show a short screen-reader-announced confirmation or error message. */
function toast(message) {
  const node = $('#toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 2800);
}
/** Load live analysis data, then fall back to the labeled local example if unavailable. */
async function loadDashboard() {
  try {
    const response = await fetch('/api/dashboard', {headers:{Accept:'application/json'}});
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const payload = await response.json();
    if (!payload.ready) throw new Error(payload.message || 'Pipeline data is not ready');
    apiAvailable = true; dashboardSummary = payload.summary; clusters = payload.clusters;
  } catch {
    apiAvailable = false;
    clusters = DEMO_CLUSTERS.map((item) => ({...item,status:localStorage.getItem(`incidentlens-review:${item.id}`)||item.status,systems:[...item.systems],causes:item.causes.map((cause)=>({...cause,evidence:[...cause.evidence]}))}));
    dashboardSummary = {incident_count:2481,cluster_count:clusters.length,proposal_count:1,review_count:2,system_count:7};
  }
  selectedId = clusters[0]?.id || null;
  if (apiAvailable && selectedId) {
    try { const response = await fetch(`/api/clusters/${encodeURIComponent(selectedId)}`); if (response.ok) Object.assign(clusters[0], await response.json()); } catch { /* the list remains usable if detail loading fails */ }
  }
  renderSummary(); renderRows(); if (selectedId) renderDetail(selectedId);
}

// This click handler fetches full incident evidence only when a user opens a row.
rows.addEventListener('click', async (event) => {
  const row = event.target.closest('tr[data-id]'); if (!row) return;
  const id = row.dataset.id;
  if (apiAvailable) {
    try { const response = await fetch(`/api/clusters/${encodeURIComponent(id)}`); if (response.ok) Object.assign(clusters.find((item)=>item.id===id), await response.json()); }
    catch { toast('Could not load cluster details.'); }
  }
  renderDetail(id);
});
// This keyboard handler makes table rows operable without a mouse.
rows.addEventListener('keydown', (event) => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('tr[data-id]')) { event.preventDefault(); event.target.click(); }
});
$('#search-input').addEventListener('input', renderRows);
$('#status-filter').addEventListener('change', renderRows);
// This handler toggles cluster-count sort order and announces the result.
$('#sort-button').addEventListener('click', () => { sortDescending = !sortDescending; renderRows(); toast(`Sorted by incident count: ${sortDescending ? 'highest first' : 'lowest first'}`); });
// This handler saves an explicit human proposal action to the configured review store.
$('#propose-button').addEventListener('click', async () => {
  const item = clusters.find((cluster) => cluster.id === selectedId); if (!item || item.status !== 'needs_review') return;
  const button = $('#propose-button');
  button.disabled = true;
  try {
    if (apiAvailable) {
      // Confirm the server saved the review before updating the visible cluster state.
      const response = await fetch(`/api/clusters/${encodeURIComponent(item.id)}/review`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'proposed'})});
      if (!response.ok) throw new Error(`Review endpoint returned ${response.status}`);
    } else {
      // Keep preview-only decisions in this browser and clearly label the sample mode.
      localStorage.setItem(`incidentlens-review:${item.id}`,'proposed');
    }
    item.status = 'proposed'; renderDetail(selectedId); renderSummary(); toast(`Proposal saved for ${item.id}. Human review required.`);
  } catch {
    // Show a clear failure message and leave the cluster in its prior review state.
    toast('Could not save the proposal. Check the connection and try again.');
  } finally {
    button.disabled = item.status !== 'needs_review';
  }
});
// This handler refreshes analysis data without losing the current page context.
$('#refresh-button').addEventListener('click', async (event) => {
  const button = event.currentTarget; button.disabled = true; button.querySelector('.button-icon').textContent = '…';
  if (apiAvailable) await loadDashboard();
  button.disabled = false; button.querySelector('.button-icon').textContent = '↻'; toast(apiAvailable ? 'Analysis results reloaded.' : 'Showing the sample preview. Start the API for pipeline results.');
});
// This handler downloads the currently loaded cluster summary as CSV.
$('#export-button').addEventListener('click', () => {
  const csv = ['cluster_id,title,incident_count,first_seen,confidence,status', ...clusters.map((item) => [item.id,`"${item.title.replaceAll('"','""')}"`,item.count,item.first_seen,item.confidence,item.status].join(','))].join('\n');
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); link.download = 'incidentlens-clusters.csv'; link.click(); URL.revokeObjectURL(link.href); toast('Cluster view exported as CSV.');
});
// This handler clears search and status filters so every cluster is visible.
$('#view-all').addEventListener('click', () => { $('#status-filter').value = 'all'; $('#search-input').value = ''; renderRows(); toast(`Showing ${clusters.length} available clusters.`); });
// This global keyboard handler supports the search shortcut and Escape-to-clear behavior.
document.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); $('#search-input').focus(); }
  if (event.key === 'Escape') { $('#search-input').value = ''; renderRows(); $('#search-input').blur(); setMobileNavOpen(false); }
});
mobileMenuButton.addEventListener('click', () => setMobileNavOpen(mobileMenuButton.getAttribute('aria-expanded') !== 'true'));
mobileNavBackdrop.addEventListener('click', () => setMobileNavOpen(false));
document.querySelectorAll('#main-navigation a').forEach((link) => link.addEventListener('click', () => setMobileNavOpen(false)));
$('#copyright-year').textContent = String(new Date().getFullYear());
loadDashboard();
