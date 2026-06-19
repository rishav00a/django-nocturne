/* Watchdog APM — dashboard.js */

const TF_BUCKET_LABEL = {
  '15m': '5min', '30m': '5min', '1h': '5min',
  '3h': '15min', '6h': '15min',
  '12h': '30min', '24h': '30min',
  '7d': '2hr',
};
const TF_FULL_LABEL = {
  '15m': '15 MINS', '30m': '30 MINS', '1h': '60 MINS',
  '3h': '3H', '6h': '6H', '12h': '12H', '24h': '24H', '7d': '7 DAYS',
};
const TF_UPPER = {
  '15m': '15M', '30m': '30M', '1h': '1H',
  '3h': '3H', '6h': '6H', '12h': '12H', '24h': '24H', '7d': '7D',
};

let errorChart, healthChart, levelChart, slowestChart, volumeChart;
let countdown = 30;
let refreshTimer;
let dataUrl, detectUrl, logsUrl;
let _anomalyData = [];
let _lastData = null;
let _lastWebhookEvents = [];
let _logPage = 1;
let _logData = {};
let _logExpandedId = null;
let currentTimeframe = localStorage.getItem('nc_timeframe') || '1h';

function initDashboard(dUrl, detUrl, lUrl) {
  dataUrl   = dUrl;
  detectUrl = detUrl;
  logsUrl   = lUrl;

  document.querySelectorAll('.tf-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      fetchDashboardData(btn.dataset.tf);
      countdown = 30;
    });
  });

  fetchDashboardData(currentTimeframe);
  startCountdown();
  initModal();
  initLogExplorer();
}

/* ── Timeframe helpers ── */

function updatePillUI(tf) {
  document.querySelectorAll('.tf-pill').forEach(btn => {
    btn.classList.toggle('tf-active', btn.dataset.tf === tf);
  });
}

function updateStatLabels(tf) {
  const u = TF_UPPER[tf] || tf.toUpperCase();
  const el = (id, txt) => { const e = document.getElementById(id); if (e) e.textContent = txt; };
  el('stat-label-total',     'TOTAL LOGS (' + u + ')');
  el('stat-label-error',     'ERROR RATE (' + u + ')');
  el('stat-label-anomalies', 'ACTIVE ANOMALIES (' + u + ')');
}

function updateChartHeaders(tf) {
  const bucket = TF_BUCKET_LABEL[tf] || '5min';
  const full   = TF_FULL_LABEL[tf]   || tf.toUpperCase();
  const u      = TF_UPPER[tf]        || tf.toUpperCase();
  const h1 = document.getElementById('h-error-rate');
  if (h1) h1.textContent = 'Error Rate / ' + bucket + ' (Last ' + full + ')';
  const h2 = document.getElementById('h-level-dist');
  if (h2) h2.textContent = 'Log Level Distribution (' + u + ')';
}

function setLoadingState(loading) {
  const bar = document.querySelector('.tf-bar');
  if (bar) bar.classList.toggle('tf-loading', loading);
}

/* ── Central data fetch (Promise.all for dash + health + anomalies) ── */

async function fetchDashboardData(tf) {
  if (tf) currentTimeframe = tf;
  localStorage.setItem('nc_timeframe', currentTimeframe);
  updatePillUI(currentTimeframe);
  setLoadingState(true);

  const params      = new URLSearchParams({ timeframe: currentTimeframe });
  const healthUrl   = dataUrl.replace('api/dashboard/data/', 'api/health/');
  const anomalyUrl  = dataUrl.replace('api/dashboard/data/', 'api/anomalies/');
  const whEventsUrl = dataUrl.replace('api/dashboard/data/', 'api/webhooks/events/') + '?limit=5';
  const whCfgUrl    = dataUrl.replace('api/dashboard/data/', 'api/webhooks/');

  try {
    const [dashResp, healthResp, anomalyResp, whEvResp, whCfgResp] = await Promise.all([
      fetch(dataUrl    + '?' + params, { credentials: 'same-origin' }),
      fetch(healthUrl  + '?' + params, { credentials: 'same-origin' }),
      fetch(anomalyUrl + '?' + params, { credentials: 'same-origin' }),
      fetch(whEventsUrl,               { credentials: 'same-origin' }),
      fetch(whCfgUrl,                  { credentials: 'same-origin' }),
    ]);

    if (!dashResp.ok || !healthResp.ok) throw new Error('API error ' + dashResp.status);

    const [dash, health, anomalies, whEvents, whConfigs] = await Promise.all([
      dashResp.json(), healthResp.json(), anomalyResp.json(),
      whEvResp.ok ? whEvResp.json() : [],
      whCfgResp.ok ? whCfgResp.json() : [],
    ]);

    _lastData = dash;
    _lastWebhookEvents = Array.isArray(whEvents) ? whEvents : [];

    updateStatLabels(currentTimeframe);
    updateChartHeaders(currentTimeframe);
    renderStats(health);
    renderIntelBar(dash);
    renderErrorChart(dash);
    renderHealthChart(dash);
    renderLevelChart(dash);
    renderSlowestEndpoints(dash);
    renderRequestVolume(dash);
    renderServiceStatus(dash);
    renderAnomalyTable(Array.isArray(anomalies) ? anomalies : []);
    renderWebhookActivity(_lastWebhookEvents, Array.isArray(whConfigs) ? whConfigs : []);
    renderHealthTrends(dash.health_trends || {});
    populateServiceFilter(dash);
    fetchLogs(1);
  } catch (e) {
    console.error('Watchdog dashboard fetch failed:', e);
  } finally {
    setLoadingState(false);
  }
}

function loadData() { return fetchDashboardData(); }

/* ── Stat cards (health data passed directly) ── */

function renderStats(h) {
  document.getElementById('stat-total').textContent      = h.total_logs      ?? '—';
  document.getElementById('stat-error-rate').textContent = (h.error_rate     ?? '—') + '%';
  document.getElementById('stat-anomalies').textContent  = h.active_anomalies ?? '—';
}

/* ── Intel bar ── */

function renderIntelBar(d) {
  const bar = document.getElementById('intel-bar');
  if (!bar) return;
  const backend  = d.ai_backend_name || '—';
  const model    = d.ai_model_name   || '—';
  const rows     = d.recent_anomalies || [];
  const lastScan = rows.length ? timeSince(new Date(rows[0].detected_at)) : 'no scans yet';
  const active   = d.active_anomalies ?? '—';
  const resolved = d.resolved_today   ?? '—';
  bar.innerHTML =
    '<span class="intel-item">AI Engine: ' + escHtml(backend) + ' (' + escHtml(model) + ')</span>' +
    '<span class="intel-sep">|</span>' +
    '<span class="intel-item">Last Scan: ' + lastScan + '</span>' +
    '<span class="intel-sep">|</span>' +
    '<span class="intel-item">Active Anomalies: ' + active + '</span>' +
    '<span class="intel-sep">|</span>' +
    '<span class="intel-item">Auto-resolved today: ' + resolved + '</span>';
}

/* ── Charts ── */

function renderErrorChart(d) {
  const ctx = document.getElementById('errorChart').getContext('2d');
  const palette = ['#00e5ff','#ff4081','#ffd740','#69f0ae','#ea80fc','#40c4ff'];
  const datasets = (d.services || []).map((s, i) => ({
    label: s,
    data: d.error_series[s] || [],
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '22',
    tension: 0.4, fill: true, pointRadius: 3,
  }));
  if (errorChart) errorChart.destroy();
  errorChart = new Chart(ctx, {
    type: 'line',
    data: { labels: d.labels || [], datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#555', maxTicksLimit: 12 }, grid: { color: '#1e2433' } },
        y: { ticks: { color: '#555' }, grid: { color: '#1e2433' }, beginAtZero: true },
      },
    },
  });
}

function renderHealthChart(d) {
  const ctx = document.getElementById('healthChart').getContext('2d');
  const scores = d.health_scores || {};
  const trends = d.health_trends || {};
  const labels = Object.keys(scores);
  const values = Object.values(scores);
  const colors = values.map(v => v >= 70 ? '#69f0ae' : v >= 40 ? '#ffd740' : '#ff4081');

  // Chart.js inline plugin: draws trend arrows above bars
  const trendArrowPlugin = {
    id: 'trendArrows',
    afterDatasetsDraw(chart) {
      const { ctx: c, scales: { x, y } } = chart;
      labels.forEach((svc, i) => {
        const t = trends[svc];
        if (!t) return;
        const arrow = t.trend === 'improving' ? '↑' : t.trend === 'degrading' ? '↓' : '→';
        const color = t.trend === 'improving' ? '#00ff88' : t.trend === 'degrading' ? '#ff4444' : '#888';
        const barX = x.getPixelForValue(i);
        const barY = y.getPixelForValue(values[i]) - 8;
        c.save();
        c.font = 'bold 14px sans-serif';
        c.fillStyle = color;
        c.textAlign = 'center';
        c.fillText(arrow, barX, barY);
        c.restore();
      });
    },
  };

  if (healthChart) healthChart.destroy();
  healthChart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Health Score', data: values, backgroundColor: colors, borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel(item) {
              const t = trends[item.label];
              if (!t) return '';
              const arrow = t.trend === 'improving' ? '▲' : t.trend === 'degrading' ? '▼' : '→';
              const sign = t.change >= 0 ? '+' : '';
              return `1h ago: ${t['1h_ago']} | Change: ${sign}${t.change} ${arrow}`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: '#aaa' }, grid: { color: '#1e2433' } },
        y: { min: 0, max: 100, ticks: { color: '#aaa' }, grid: { color: '#1e2433' } },
      },
    },
    plugins: [trendArrowPlugin],
  });
}

function renderLevelChart(d) {
  const ctx = document.getElementById('levelChart').getContext('2d');
  const ld = d.level_distribution || {};
  const levelColors = { INFO: '#00e5ff', WARNING: '#ffd740', ERROR: '#ff4081', CRITICAL: '#ea80fc' };
  if (levelChart) levelChart.destroy();
  levelChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(ld),
      datasets: [{
        data: Object.values(ld),
        backgroundColor: Object.keys(ld).map(k => levelColors[k] || '#555'),
        borderWidth: 2, borderColor: '#0f1117',
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { color: '#aaa', boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

/* ── Widget A: Slowest Endpoints ── */

function renderSlowestEndpoints(d) {
  const eps = d.slowest_endpoints || [];
  const ctx = document.getElementById('slowestChart');
  if (!ctx) return;
  if (!eps.length) {
    const noData = ctx.closest('.mini-card').querySelector('p.no-data');
    if (noData) noData.style.display = 'block';
    return;
  }
  const maxMs = eps[0].avg_ms || 1;
  const colors = eps.map(e => {
    const t = Math.min(e.avg_ms / maxMs, 1);
    const r = Math.round(t * 255);
    const g = Math.round(229 * (1 - t) + 107 * t);
    const b = Math.round(255 * (1 - t) + 107 * t);
    return 'rgba(' + r + ',' + g + ',' + b + ',0.85)';
  });
  if (slowestChart) slowestChart.destroy();
  slowestChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: eps.map(e => e.request_path.length > 22 ? '…' + e.request_path.slice(-22) : e.request_path),
      datasets: [{ data: eps.map(e => Math.round(e.avg_ms)), backgroundColor: colors, borderRadius: 3 }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: item => Math.round(item.raw) + 'ms',
            title: items => eps[items[0].dataIndex].request_path,
          },
        },
      },
      scales: {
        x: { ticks: { color: '#555', callback: v => v + 'ms' }, grid: { color: '#1e2433' } },
        y: { ticks: { color: '#aaa', font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
}

/* ── Widget B: Request Volume Sparkline ── */

function renderRequestVolume(d) {
  const vol = d.request_volume || [];
  const ctx = document.getElementById('volumeChart');
  if (!ctx || !vol.length) return;
  if (volumeChart) volumeChart.destroy();
  volumeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: vol.map(v => v.bucket),
      datasets: [{
        data: vol.map(v => v.count),
        borderColor: '#00e5ff',
        backgroundColor: '#00e5ff22',
        tension: 0.4, fill: true, pointRadius: 0, borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { title: items => items[0].label, label: item => item.raw + ' reqs' },
      }},
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
    },
  });
}

/* ── Widget C: Service Status Board ── */

function renderServiceStatus(d) {
  const board = document.getElementById('service-status-board');
  if (!board) return;
  const scores   = d.health_scores || {};
  const services = Object.keys(scores);
  if (!services.length) {
    board.innerHTML = '<div style="color:#555;font-size:0.78rem">No services detected.</div>';
    return;
  }
  const lastIncident = {};
  (d.recent_anomalies || []).forEach(a => {
    if (!lastIncident[a.service_name]) lastIncident[a.service_name] = a.detected_at;
  });
  board.innerHTML = services.map(svc => {
    const score  = scores[svc];
    const color  = score >= 70 ? '#69f0ae' : score >= 40 ? '#ffd740' : '#ff4081';
    const label  = score >= 70 ? '● HEALTHY' : score >= 40 ? '● DEGRADED' : '● CRITICAL';
    const inc    = lastIncident[svc];
    const incStr = inc ? 'Last: ' + timeSince(new Date(inc)) : 'No incidents';
    return '<div class="svc-card" style="border-left:3px solid ' + color + '">' +
      '<div class="svc-name" title="' + escHtml(svc) + '">' + escHtml(svc) + '</div>' +
      '<div class="svc-score">' + (score != null ? Math.round(score) : '—') + ' / 100</div>' +
      '<div class="svc-status" style="color:' + color + '">' + label + '</div>' +
      '<div class="svc-incident">' + incStr + '</div>' +
      '</div>';
  }).join('');
}

/* ── Anomaly table (receives flat array from anomaly endpoint) ── */

function renderAnomalyTable(anomalies) {
  _anomalyData = anomalies;
  const tbody = document.getElementById('anomaly-tbody');
  if (!_anomalyData.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#555;text-align:center">No anomalies in selected timeframe.</td></tr>';
    return;
  }
  tbody.innerHTML = _anomalyData.map((a, i) =>
    '<tr class="anomaly-row" data-idx="' + i + '" title="Click for details">' +
      '<td>' + new Date(a.detected_at).toLocaleString() + '</td>' +
      '<td>' + escHtml(a.service_name) + '</td>' +
      '<td><span class="badge badge-' + a.severity + '">' + a.severity + '</span></td>' +
      '<td>' + a.z_score.toFixed(2) + '</td>' +
      '<td>' + (a.error_count ?? '—') + '</td>' +
      '<td style="color:' + ((a.health_score||0) >= 70 ? '#69f0ae' : (a.health_score||0) >= 40 ? '#ffd740' : '#ff4081') + '">' +
        (a.health_score != null ? a.health_score.toFixed(1) : '—') +
      '</td>' +
      '<td>' + (a.resolved ? '<span style="color:#69f0ae">✓</span>' : '<span style="color:#ff4081">✗</span>') + '</td>' +
    '</tr>'
  ).join('');
  tbody.querySelectorAll('.anomaly-row').forEach(tr => {
    tr.addEventListener('click', () => openModal(_anomalyData[+tr.dataset.idx]));
  });
}

/* ── Anomaly detail modal ── */

function initModal() {
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
  const wrap = document.getElementById('anomaly-modal');
  if (wrap) wrap.addEventListener('click', e => { if (e.target === wrap) closeModal(); });
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
}

function openModal(a) {
  document.getElementById('modal-content').innerHTML = buildModalHTML(a);
  document.getElementById('anomaly-modal').style.display = 'flex';
  document.getElementById('modal-resolve-btn')?.addEventListener('click', () => {
    if (!a.resolved) resolveAnomaly(a);
  });
  document.getElementById('modal-detect-btn')?.addEventListener('click', runDetectionFromModal);
}

function closeModal() {
  document.getElementById('anomaly-modal').style.display = 'none';
}

function buildModalHTML(a) {
  const dt = new Date(a.detected_at);
  const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    + ' ' + dt.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const z   = Math.max(0, Math.min(a.z_score, 6));
  const pct = (z / 6 * 100).toFixed(1);
  const zTexts = {
    MEDIUM:   'This is a moderate deviation worth investigating.',
    HIGH:     'This is a significant spike that likely impacted users.',
    CRITICAL: 'This is an extreme spike indicating a serious incident.',
  };
  const winStr = (a.window_start && a.window_end)
    ? new Date(a.window_start).toLocaleTimeString() + ' → ' + new Date(a.window_end).toLocaleTimeString()
    : '—';
  const diag = (a.ai_diagnosis || '').trim();
  const diagHidden = !diag || diag.includes('not configured') || diag.includes('disabled')
    || diag.includes('AI diagnosis disabled');
  let aiSection = '';
  if (!diagHidden) {
    const diagAt = a.ai_diagnosed_at ? new Date(a.ai_diagnosed_at).toLocaleString() : '—';
    const be = _lastData ? _lastData.ai_backend_name : '';
    const mo = _lastData ? _lastData.ai_model_name   : '';
    aiSection = '<div class="modal-section">' +
      '<div class="modal-section-title">AI Root-Cause Analysis</div>' +
      '<div class="ai-terminal">' + escHtml(diag) + '</div>' +
      '<div style="font-size:0.7rem;color:#555;margin-top:8px;">Diagnosed at ' + diagAt +
        (be ? ' using ' + escHtml(be) + ' (' + escHtml(mo) + ')' : '') + '</div>' +
      '</div>';
  }
  const resolveBtn = a.resolved
    ? '<button id="modal-resolve-btn" disabled style="opacity:0.45;cursor:default">Already Resolved</button>'
    : '<button id="modal-resolve-btn">Mark as Resolved</button>';
  return (
    '<div class="modal-header">' +
      '<span style="color:#00e5ff;font-size:1.05rem;font-weight:bold">' + escHtml(a.service_name) + '</span>' +
      '<span class="badge badge-' + a.severity + '" style="margin-left:12px">' + a.severity + '</span>' +
      '<span style="margin-left:12px;font-size:0.8rem">' +
        (a.resolved ? '<span style="color:#69f0ae">Resolved</span>' : '<span style="color:#ff4081">Active</span>') +
      '</span>' +
    '</div>' +
    '<div class="modal-section">' +
      '<div class="modal-section-title">Anomaly Summary</div>' +
      '<div class="modal-grid">' +
        '<div class="modal-label">Detected At</div><div>' + dateStr + '</div>' +
        '<div class="modal-label">Service</div><div>' + escHtml(a.service_name) + '</div>' +
        '<div class="modal-label">Severity</div><div><span class="badge badge-' + a.severity + '">' + a.severity + '</span></div>' +
        '<div class="modal-label">Status</div><div>' + (a.resolved ? 'Resolved' : 'Active') + '</div>' +
        '<div class="modal-label">Error Count</div><div>' + (a.error_count ?? '—') + ' errors in window</div>' +
        '<div class="modal-label">Window</div><div>' + winStr + '</div>' +
      '</div>' +
    '</div>' +
    '<div class="modal-section">' +
      '<div class="modal-section-title">Z-Score Analysis</div>' +
      '<div class="zscore-bar-wrap">' +
        '<div class="zscore-bar">' +
          '<div class="zscore-zone" style="width:33.3%;background:#28a74530;border-radius:4px 0 0 4px"></div>' +
          '<div class="zscore-zone" style="width:16.7%;background:#ffc10730"></div>' +
          '<div class="zscore-zone" style="width:16.7%;background:#fd7e1430"></div>' +
          '<div class="zscore-zone" style="width:33.3%;background:#dc354530;border-radius:0 4px 4px 0"></div>' +
          '<div class="zscore-marker" style="left:' + pct + '%"></div>' +
        '</div>' +
        '<div class="zscore-labels">' +
          '<span style="color:#28a745">0 Normal</span>' +
          '<span style="color:#ffc107">2 Medium</span>' +
          '<span style="color:#fd7e14">3 High</span>' +
          '<span style="color:#dc3545">4 Critical</span>' +
          '<span style="color:#666">6+</span>' +
        '</div>' +
      '</div>' +
      '<p class="zscore-explain">' +
        'A Z-score of <strong style="color:#e0e0e0">' + a.z_score.toFixed(2) + '</strong> means this ' +
        "service's error rate was <strong style=\"color:#e0e0e0\">" + a.z_score.toFixed(1) + 'x</strong> ' +
        'standard deviations above its normal baseline. ' + escHtml(zTexts[a.severity] || '') +
      '</p>' +
    '</div>' +
    aiSection +
    buildWebhookModalSection(a) +
    '<div class="modal-actions">' +
      resolveBtn +
      '<button id="modal-detect-btn">Run Fresh Detection</button>' +
      '<span id="modal-action-status"></span>' +
    '</div>'
  );
}

function buildWebhookModalSection(a) {
  const title = '<div class="modal-section-title">Webhook Delivery</div>';

  if (!a.webhook_triggered) {
    return '<div class="modal-section">' + title +
      '<div class="wh-modal-entry" style="color:#888">' +
        '&#x26A0; No webhook configured at time of detection. ' +
        '<a href="#wh-config-info" onclick="closeModal()" style="color:#00e5ff;text-decoration:none">Configure Webhook ↓</a>' +
      '</div>' +
    '</div>';
  }

  // Find matching event from _lastWebhookEvents (populated when dashboard loads)
  const ev = (_lastWebhookEvents || []).find(e => e.anomaly === a.id);
  if (!ev) {
    return '<div class="modal-section">' + title +
      '<div class="wh-modal-entry wh-modal-ok">&#x2705; Webhook was triggered for this anomaly.</div>' +
    '</div>';
  }

  const ts = timeSince(new Date(ev.triggered_at));
  const masked = ev.webhook_url ? maskUrl(ev.webhook_url) : '—';
  const payloadId = 'wh-payload-' + a.id;

  if (ev.success) {
    return '<div class="modal-section">' + title +
      '<div class="wh-modal-entry wh-modal-ok">&#x2705; Delivered to ' + escHtml(masked) + '</div>' +
      '<div class="wh-modal-entry" style="color:#555">Status: ' + (ev.response_status || '?') + ' OK · ' + ts + '</div>' +
      '<div style="margin-top:6px"><button class="wh-payload-btn" onclick="togglePayload(\'' + payloadId + '\')">View Payload</button></div>' +
      '<pre class="wh-payload-pre" id="' + payloadId + '">' + escHtml(JSON.stringify(ev.payload, null, 2)) + '</pre>' +
    '</div>';
  }

  return '<div class="modal-section">' + title +
    '<div class="wh-modal-entry wh-modal-err">&#x274C; Delivery failed</div>' +
    '<div class="wh-modal-entry" style="color:#888">Error: ' + escHtml(ev.error_message || '—') + '</div>' +
    '<div style="margin-top:8px"><button id="wh-retry-btn" onclick="sendTestWebhook()" style="font-size:0.76rem">&#x21BB; Retry Webhook</button></div>' +
  '</div>';
}

function togglePayload(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

function maskUrl(url) {
  try {
    const u = new URL(url);
    const host = u.hostname;
    if (host.length > 10) {
      return u.protocol + '//' + host.slice(0, 3) + '***' + host.slice(-4) + u.pathname.slice(0, 8) + '…';
    }
    return url;
  } catch { return url; }
}

async function resolveAnomaly(a) {
  const btn = document.getElementById('modal-resolve-btn');
  const st  = document.getElementById('modal-action-status');
  btn.disabled = true;
  st.style.color = '#aaa'; st.textContent = 'Resolving…';
  const url = dataUrl.replace('api/dashboard/data/', 'api/anomalies/' + a.id + '/');
  try {
    const r = await fetch(url, {
      method: 'PATCH', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ resolved: true }),
    });
    if (r.ok) {
      a.resolved = true;
      st.style.color = '#69f0ae'; st.textContent = 'Marked as resolved';
      btn.textContent = 'Already Resolved';
      fetchDashboardData();
    } else {
      st.style.color = '#ff4081'; st.textContent = 'Failed (check permissions).';
      btn.disabled = false;
    }
  } catch (e) {
    st.style.color = '#ff4081'; st.textContent = 'Error: ' + e.message;
    btn.disabled = false;
  }
}

async function runDetectionFromModal() {
  const btn = document.getElementById('modal-detect-btn');
  const st  = document.getElementById('modal-action-status');
  btn.disabled = true;
  st.style.color = '#aaa'; st.textContent = 'Running scan…';
  try {
    const r = await fetch(detectUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const d = await r.json();
    st.style.color = '#69f0ae';
    st.textContent = 'Scan complete — ' + d.anomalies_detected + ' anomalies found.';
    fetchDashboardData();
  } catch (e) {
    st.style.color = '#ff4081'; st.textContent = 'Scan failed: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

async function runDetection() {
  try {
    const r = await fetch(detectUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const d = await r.json();
    alert('Detection scan complete — ' + d.anomalies_detected + ' anomalies found.');
    fetchDashboardData();
  } catch (e) {
    alert('Detection scan failed: ' + e.message);
  }
}

/* ── Log Explorer ── */

function populateServiceFilter(d) {
  const sel = document.getElementById('log-filter-service');
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">All Services</option>';
  (d.services || []).forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    if (s === cur) opt.selected = true;
    sel.appendChild(opt);
  });
}

function initLogExplorer() {
  const search = document.getElementById('log-filter-search');
  if (search) {
    let debounce;
    search.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => fetchLogs(1), 400);
    });
  }
  document.getElementById('log-filter-service')?.addEventListener('change', () => fetchLogs(1));
  document.getElementById('log-filter-level')?.addEventListener('change',   () => fetchLogs(1));
  document.getElementById('log-page-size')?.addEventListener('change',      () => fetchLogs(1));
  document.getElementById('log-prev-btn')?.addEventListener('click',  () => { if (_logPage > 1) fetchLogs(_logPage - 1); });
  document.getElementById('log-next-btn')?.addEventListener('click',  () => fetchLogs(_logPage + 1));
  document.getElementById('log-apply-btn')?.addEventListener('click', () => fetchLogs(1));
  document.getElementById('log-clear-btn')?.addEventListener('click', clearLogFilters);
}

function clearLogFilters() {
  const s = document.getElementById('log-filter-service');
  const l = document.getElementById('log-filter-level');
  const q = document.getElementById('log-filter-search');
  if (s) s.value = '';
  if (l) l.value = '';
  if (q) q.value = '';
  fetchLogs(1);
}

async function fetchLogs(page) {
  _logPage = page;
  const service  = document.getElementById('log-filter-service')?.value || '';
  const level    = document.getElementById('log-filter-level')?.value   || '';
  const search   = document.getElementById('log-filter-search')?.value  || '';
  const pageSize = document.getElementById('log-page-size')?.value      || '25';

  const params = new URLSearchParams({ page, page_size: pageSize, timeframe: currentTimeframe });
  if (service) params.set('service', service);
  if (level)   params.set('level', level);
  if (search)  params.set('search', search);

  const tbody = document.getElementById('log-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="color:#555;text-align:center">Loading…</td></tr>';

  try {
    const r = await fetch(logsUrl + '?' + params, { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();

    const ps         = +pageSize;
    const totalPages = Math.max(1, Math.ceil((data.count || 0) / ps));
    const from       = (page - 1) * ps + 1;
    const to         = from + (data.results || []).length - 1;

    const lbl = document.getElementById('log-count-label');
    if (lbl) lbl.textContent = data.count ? 'Showing ' + from + '–' + to + ' of ' + data.count + ' logs' : 'No logs found';

    const pgl = document.getElementById('log-page-label');
    if (pgl) pgl.textContent = 'Page ' + page + ' of ' + totalPages;

    const prev = document.getElementById('log-prev-btn');
    const next = document.getElementById('log-next-btn');
    if (prev) prev.disabled = page <= 1;
    if (next) next.disabled = page >= totalPages;

    renderLogTable(data.results || []);
  } catch (e) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="color:#ff4081;text-align:center">Error: ' + escHtml(e.message) + '</td></tr>';
  }
}

function renderLogTable(logs) {
  const tbody = document.getElementById('log-tbody');
  if (!logs.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:#555;text-align:center">No logs found.</td></tr>';
    return;
  }
  _logData = {};
  logs.forEach(l => { _logData[l.id] = l; });
  _logExpandedId = null;

  tbody.innerHTML = logs.map(log => {
    const ts = new Date(log.timestamp).toLocaleString();
    const rt = log.response_time_ms;
    const rtColor = rt == null ? '#555' : rt < 200 ? '#69f0ae' : rt < 500 ? '#ffd740' : '#ff4081';
    const msg = (log.message || '').substring(0, 60);
    return '<tr class="log-row" id="log-row-' + log.id + '">' +
      '<td style="white-space:nowrap;font-size:0.73rem"><span class="log-chevron" style="color:#444;margin-right:6px;user-select:none">▼</span>' + ts + '</td>' +
      '<td>' + escHtml(log.service_name || '—') + '</td>' +
      '<td><span class="level-badge level-' + log.level + '">' + log.level + '</span></td>' +
      '<td class="ellipsis" title="' + escHtml(log.request_path || '') + '">' + escHtml(log.request_path || '—') + '</td>' +
      '<td>' + (log.status_code || '—') + '</td>' +
      '<td style="color:' + rtColor + '">' + (rt != null ? rt + 'ms' : '—') + '</td>' +
      '<td class="ellipsis" title="' + escHtml(log.message || '') + '">' + escHtml(msg) + ((log.message||'').length > 60 ? '…' : '') + '</td>' +
      '</tr>';
  }).join('');

  tbody.querySelectorAll('.log-row').forEach(tr => {
    tr.addEventListener('click', () => toggleLogRow(_logData[+tr.id.replace('log-row-', '')]));
  });
}

async function toggleLogRow(listLog) {
  if (!listLog) return;
  const existingId = 'log-detail-' + listLog.id;
  const existing   = document.getElementById(existingId);

  // Collapse if clicking the already-expanded row
  if (existing) {
    existing.remove();
    const prevTr = document.getElementById('log-row-' + listLog.id);
    if (prevTr) { const ch = prevTr.querySelector('.log-chevron'); if (ch) ch.textContent = '▼'; }
    if (_logExpandedId === listLog.id) { _logExpandedId = null; return; }
  }

  // Collapse any other open row
  if (_logExpandedId !== null && _logExpandedId !== listLog.id) {
    const prevDetail = document.getElementById('log-detail-' + _logExpandedId);
    if (prevDetail) prevDetail.remove();
    const prevTr = document.getElementById('log-row-' + _logExpandedId);
    if (prevTr) { const ch = prevTr.querySelector('.log-chevron'); if (ch) ch.textContent = '▼'; }
  }

  _logExpandedId = listLog.id;
  const tr = document.getElementById('log-row-' + listLog.id);
  if (!tr) return;

  const chevron = tr.querySelector('.log-chevron');
  if (chevron) chevron.textContent = '▲';

  // Insert shimmer immediately
  const detailTr = document.createElement('tr');
  detailTr.id        = existingId;
  detailTr.className = 'log-detail-row';
  detailTr.innerHTML = '<td colspan="7">' + buildLogShimmer() + '</td>';
  tr.after(detailTr);

  try {
    const r = await fetch(logsUrl + listLog.id + '/', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const fullLog = await r.json();

    const cell = detailTr.querySelector('td');
    if (cell) {
      cell.innerHTML = buildLogDetailHTML(fullLog);
      // If cached analysis exists, display it immediately (State D)
      if (fullLog.ai_analysis) {
        renderCachedAnalysis(fullLog);
      }
      // Bind analyse button (State A → B → C)
      document.getElementById('log-analyse-btn-' + fullLog.id)
        ?.addEventListener('click', e => { e.stopPropagation(); analyseLog(fullLog); });
    }
  } catch (e) {
    const cell = detailTr.querySelector('td');
    if (cell) {
      cell.innerHTML = '<div style="padding:16px;color:#ff4081">Error loading details: ' + escHtml(e.message) + '</div>';
    }
  }
}

function buildLogShimmer() {
  return '<div class="log-shimmer">' +
    '<div class="log-shimmer-bar" style="width:55%"></div>' +
    '<div class="log-shimmer-bar" style="width:35%;margin-top:8px"></div>' +
    '<div class="log-shimmer-bar" style="width:70%;margin-top:8px"></div>' +
    '</div>';
}

function buildLogDetailHTML(log) {
  const isErr  = log.level === 'ERROR' || log.level === 'CRITICAL';
  const isWarn = log.level === 'WARNING';

  const leftCol  = buildErrorLeftCol(log);

  if (isErr) {
    return '<div class="log-detail-inner log-detail-two-col">' +
      '<div class="log-detail-col ldc-left">' + leftCol + '</div>' +
      '<div class="log-detail-col ldc-right">' + buildAIRightCol(log) + '</div>' +
      '</div>';
  }
  return '<div class="log-detail-inner log-detail-one-col">' +
    '<div class="log-detail-col">' + leftCol + '</div>' +
    '</div>';
}

function buildErrorLeftCol(log) {
  const isErr  = log.level === 'ERROR' || log.level === 'CRITICAL';
  const isWarn = log.level === 'WARNING';

  let mainSection = '';

  if (isErr && log.exception_type && log.stacktrace) {
    // Case 1 — full exception + stacktrace
    mainSection =
      '<div class="exc-badge">' +
        '<div class="exc-type">' + escHtml(log.exception_type) + '</div>' +
        '<div class="exc-msg">' + escHtml(log.exception_message || log.message || '') + '</div>' +
      '</div>' +
      '<div class="log-detail-label" style="margin-top:12px">STACKTRACE</div>' +
      '<pre class="log-stacktrace-box" id="strace-' + log.id + '">' + renderStacktrace(log.stacktrace) + '</pre>';
  } else if (isErr) {
    // Case 2 — ERROR/CRITICAL without stacktrace
    mainSection =
      '<div class="log-detail-label">ERROR DETAIL</div>' +
      '<pre class="log-stacktrace-box" style="border-color:#ff8800;color:#ffaa55">' + escHtml(log.message || '—') + '</pre>';
  } else if (isWarn) {
    // Case 3 — WARNING
    mainSection =
      '<div class="log-detail-label">WARNING DETAIL</div>' +
      '<pre class="log-stacktrace-box" style="border-color:#ffaa00;color:#ffd740">' + escHtml(log.message || '—') + '</pre>';
  } else {
    // Case 4 — INFO
    mainSection =
      '<div class="log-detail-label">MESSAGE</div>' +
      '<div style="color:#b0bec5;font-size:0.82rem;line-height:1.6;margin-top:4px">' + escHtml(log.message || '—') + '</div>';
  }

  return mainSection +
    '<div class="log-meta-grid" style="margin-top:14px">' +
      '<span class="log-detail-key">Path</span><span>' + escHtml(log.request_path || '—') + '</span>' +
      '<span class="log-detail-key">Status</span><span>' + (log.status_code || '—') + '</span>' +
      '<span class="log-detail-key">Response Time</span><span>' + (log.response_time_ms != null ? log.response_time_ms + 'ms' : '—') + '</span>' +
      '<span class="log-detail-key">Source IP</span><span>' + escHtml(log.source_ip || '—') + '</span>' +
    '</div>';
}

function buildAIRightCol(log) {
  // Right col only for ERROR/CRITICAL (State A — awaiting click)
  return '<div class="log-detail-label">AI ANALYSIS</div>' +
    '<div id="log-ai-panel-' + log.id + '" class="ai-panel-idle">' +
      '<button id="log-analyse-btn-' + log.id + '" class="ai-analyse-btn">Analyse This Log</button>' +
      '<p class="ai-panel-hint">Get AI root cause + fix suggestions</p>' +
    '</div>';
}

function renderCachedAnalysis(log) {
  const panel = document.getElementById('log-ai-panel-' + log.id);
  if (!panel) return;
  const diagAt = log.ai_analysed_at ? timeSince(new Date(log.ai_analysed_at)) : 'some time ago';
  panel.innerHTML = buildAnalysisDisplay(log.ai_analysis, diagAt, '(cached)', true);
}

function renderStacktrace(raw) {
  const lines = (raw || '').split('\n');

  // Last non-empty, non-indented line is the exception line
  let excIdx = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (lines[i].trim() && !/^\s/.test(lines[i])) { excIdx = i; break; }
  }

  return lines.map((line, i) => {
    if (i === excIdx) {
      return '<span style="color:#ff4444;font-weight:bold">' + escHtml(line) + '</span>';
    }
    if (line.includes('File "')) {
      // Escape first, then wrap parts in color spans
      let html = escHtml(line);
      html = html.replace(/(File &quot;)([^&]*)(&quot;)/, '$1<span style="color:#00e5ff">$2</span>$3');
      html = html.replace(/(line \d+)/, '<span style="color:#ffaa00">$1</span>');
      return html;
    }
    return '<span style="color:#cccccc">' + escHtml(line) + '</span>';
  }).join('\n');
}

async function analyseLog(log) {
  const panel = document.getElementById('log-ai-panel-' + log.id);
  if (!panel) return;

  // State B — loading
  const backend = _lastData ? _lastData.ai_backend_name : 'AI';
  const model   = _lastData ? _lastData.ai_model_name   : '';
  panel.innerHTML =
    '<div class="ai-loading">' +
      '<span style="color:#00e5ff">Analysing with ' + escHtml(backend) + (model ? ' (' + escHtml(model) + ')' : '') + '…</span>' +
      '<span class="ai-dots"><span>.</span><span>.</span><span>.</span></span>' +
    '</div>';

  try {
    const r = await fetch(logsUrl + log.id + '/analyse/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();

    // Update in-memory log so re-expand skips button
    log.ai_analysis    = data.analysis;
    log.ai_analysed_at = data.ai_analysed_at;

    // State C — result
    const diagAt = data.ai_analysed_at ? timeSince(new Date(data.ai_analysed_at)) : 'just now';
    panel.innerHTML = buildAnalysisDisplay(data.analysis, diagAt, escHtml(data.model), data.cached);
  } catch (e) {
    panel.innerHTML =
      '<button id="log-analyse-btn-' + log.id + '" class="ai-analyse-btn">Retry Analysis</button>' +
      '<p style="color:#ff4081;font-size:0.78rem;margin-top:8px">Error: ' + escHtml(e.message) + '</p>';
    document.getElementById('log-analyse-btn-' + log.id)
      ?.addEventListener('click', ev => { ev.stopPropagation(); analyseLog(log); });
  }
}

function buildAnalysisDisplay(text, diagAt, model, cached) {
  const points = parseAnalysisPoints(text);
  let body = '';

  if (points) {
    const titles = { '1': 'ROOT CAUSE', '2': 'IMMEDIATE FIX', '3': 'PREVENTION' };
    body = Object.entries(titles).map(([n, title]) =>
      '<div class="ai-point">' +
        '<div class="ai-point-title">' + n + '. ' + title + '</div>' +
        '<div class="ai-point-body">' + escHtml(points[n] || '—') + '</div>' +
      '</div>'
    ).join('');
  } else {
    body = '<div style="white-space:pre-wrap">' + escHtml(text) + '</div>';
  }

  return '<div class="ai-terminal">' + body + '</div>' +
    '<div class="ai-footer">' +
      (cached ? 'Cached' : 'Fresh analysis') + ' · ' + escHtml(model) + ' · ' + diagAt +
    '</div>';
}

function parseAnalysisPoints(text) {
  if (!text) return null;
  const result = {};
  // Match "1. ...", "2. ...", "3. ..." — each may span multiple lines until next marker or end
  const re = /^(\d)\.\s+(.+?)(?=^\d\.\s|\Z)/gms;
  let m;
  while ((m = re.exec(text)) !== null) {
    result[m[1]] = m[2].trim();
  }
  return (result['1'] && result['2'] && result['3']) ? result : null;
}

/* ── Webhook Activity panel (CHANGE 6) ── */

function renderWebhookActivity(events, configs) {
  const feed = document.getElementById('wh-feed');
  const cfgEl = document.getElementById('wh-config-info');

  if (cfgEl) {
    if (configs.length) {
      const c = configs[0];
      const masked = maskUrl(c.url);
      cfgEl.innerHTML =
        '<span style="color:#555">Active URL: </span>' + escHtml(masked) +
        (configs[0].is_active
          ? ' <span style="color:#69f0ae;font-size:0.7rem">● ACTIVE</span>'
          : ' <span style="color:#ff4081;font-size:0.7rem">○ INACTIVE</span>');
    } else {
      cfgEl.innerHTML = '<span style="color:#555">No webhook configured.</span>';
    }
  }

  if (!feed) return;
  if (!events.length) {
    feed.innerHTML =
      '<div class="wh-empty">No webhook events yet. Webhooks fire automatically ' +
      'when anomaly thresholds are breached.</div>';
    return;
  }

  feed.innerHTML = events.slice(0, 5).map(ev => {
    const icon = ev.success ? '&#x2705;' : '&#x274C;';
    const cls  = ev.success ? 'wh-entry-ok' : 'wh-entry-err';
    const ts   = timeSince(new Date(ev.triggered_at));
    const svc  = ev.service_name ? escHtml(ev.service_name) : 'test';
    const sev  = ev.severity ? ' (' + escHtml(ev.severity) + ')' : '';
    const err  = (!ev.success && ev.error_message) ? ' — ' + escHtml(ev.error_message.slice(0, 40)) : '';
    return '<div class="wh-entry">' +
      '<span class="wh-ts">' + ts + '</span>' +
      '<span class="' + cls + '">' + icon + ' → ' + svc + sev + err + '</span>' +
    '</div>';
  }).join('');
}

async function sendTestWebhook() {
  const btn = document.getElementById('wh-test-btn');
  const res = document.getElementById('wh-test-result');
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
  if (res) res.textContent = '';

  const testUrl = dataUrl.replace('api/dashboard/data/', 'api/webhooks/test/');
  try {
    const r = await fetch(testUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
    const data = await r.json();
    if (res) {
      if (data.success) {
        res.innerHTML = '<span style="color:#69f0ae">&#x2705; Test delivered successfully</span>';
      } else {
        const err = (data.results || []).map(x => x.error).filter(Boolean).join('; ');
        res.innerHTML = '<span style="color:#ff4081">&#x274C; Delivery failed: ' + escHtml(err || data.detail || 'unknown') + '</span>';
      }
    }
  } catch (e) {
    if (res) res.innerHTML = '<span style="color:#ff4081">&#x274C; ' + escHtml(e.message) + '</span>';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⚡ Send Test Webhook'; }
    // Refresh webhook events after test
    setTimeout(() => fetchDashboardData(), 1500);
  }
}

/* ── Health Trends panel (CHANGE 9) ── */

function renderHealthTrends(trends) {
  const grid = document.getElementById('health-trends-grid');
  if (!grid) return;

  const entries = Object.entries(trends);
  if (!entries.length) {
    grid.innerHTML = '<div style="color:#555;font-size:0.78rem">No health trend data yet. Run a detection scan to populate.</div>';
    return;
  }

  grid.innerHTML = entries.map(([svc, t]) => {
    const trendClass = t.trend;
    const arrow = t.trend === 'improving' ? '↑' : t.trend === 'degrading' ? '↓' : '→';
    const arrowLabel = t.trend.toUpperCase();
    const sign = t.change >= 0 ? '+' : '';
    const barPct = Math.max(0, Math.min(t.current, 100));
    return '<div class="ht-card ht-' + trendClass + '">' +
      '<div class="ht-svc">' +
        '<span title="' + escHtml(svc) + '">' + escHtml(svc.length > 16 ? svc.slice(0, 14) + '…' : svc) + '</span>' +
        '<span class="ht-arrow ht-' + trendClass + '">' + arrow + ' ' + arrowLabel + '</span>' +
      '</div>' +
      '<div class="ht-bar-wrap"><div class="ht-bar ht-' + trendClass + '" style="width:' + barPct + '%"></div></div>' +
      '<div class="ht-score">' + t.current.toFixed(0) + '<span style="color:#555;font-size:0.7rem">/100</span></div>' +
      '<div class="ht-prev">Was ' + t['1h_ago'].toFixed(0) + '/100 one hour ago (' + sign + t.change + ')</div>' +
    '</div>';
  }).join('');
}

/* ── Utilities ── */

function timeSince(date) {
  const secs = Math.floor((Date.now() - date) / 1000);
  if (secs < 60) return secs + ' secs ago';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return mins + ' min' + (mins !== 1 ? 's' : '') + ' ago';
  const hrs = Math.floor(mins / 60);
  return hrs + ' hr' + (hrs !== 1 ? 's' : '') + ' ago';
}

function getCookie(name) {
  const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return v ? v[2] : null;
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function startCountdown() {
  const el = document.getElementById('countdown');
  countdown = 30;
  clearInterval(refreshTimer);
  refreshTimer = setInterval(() => {
    countdown--;
    if (el) el.textContent = countdown;
    if (countdown <= 0) { countdown = 30; fetchDashboardData(); }
  }, 1000);
}
