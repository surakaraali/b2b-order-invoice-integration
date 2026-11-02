/*
 * Reads data/results.json (created by scripts/run_sql.py) and data/plan.json (created by
 * scripts/sync_site_assets.py) and fills the page: the text in the chosen language, the KPI numbers,
 * the tables, the charts and the "View SQL and result" panels. The sequence and state diagrams are
 * drawn with Mermaid only when the visitor opens that section.
 */

const REPO_FILES = `${REPO_URL}/blob/main/`; // REPO_URL comes from i18n.js
const FONT = '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif';
const MERMAID_URL = 'https://cdnjs.cloudflare.com/ajax/libs/mermaid/12.1.0/mermaid.min.js';
const UML = ['seq_01_submit_order', 'seq_02_query_stock', 'seq_03_issue_einvoice',
  'seq_04_webhook_delivery', 'state_01_order', 'state_02_invoice'];
const WIREFRAMES = ['01_order_entry', '02_order_list', '03_order_detail', '04_invoices', '05_approval_task'];
const TIMELINE = ['s1', 's2', 's3', 's4', 's5', 's6', 'pilot', 'golive'];

let lang = pickLanguage();
let results = {};
let plan = {};
let charts = [];
let umlState = 'idle'; // idle, loading or done

main();

async function main() {
  const [r, p] = await Promise.all([
    fetch('data/results.json').then(response => response.json()),
    fetch('data/plan.json').then(response => response.json()),
  ]);
  results = r;
  plan = p;

  document.querySelectorAll('[data-lang]').forEach(button => {
    button.addEventListener('click', () => setLanguage(button.dataset.lang));
  });
  document.getElementById('uml').addEventListener('toggle', event => {
    if (event.target.open) drawUml();
  });

  render();
  await document.fonts.ready; // so chart labels are drawn in IBM Plex Sans
  drawCharts();

  // Redraw with the matching colors when the visitor switches between light and dark mode.
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    drawCharts();
    if (umlState === 'done') drawUml(true);
  });
}

/* ---------- Language ---------- */

// Order of preference: ?lang= in the address, the visitor's last choice, then the browser language.
function pickLanguage() {
  const fromUrl = new URLSearchParams(location.search).get('lang');
  if (Object.hasOwn(TEXT, fromUrl ?? '')) return fromUrl;
  try {
    const saved = localStorage.getItem('lang');
    if (Object.hasOwn(TEXT, saved ?? '')) return saved;
  } catch { /* storage can be blocked, the page still works */ }
  return navigator.language.toLowerCase().startsWith('tr') ? 'tr' : 'en';
}

function setLanguage(newLang) {
  if (newLang === lang) return;
  lang = newLang;
  try { localStorage.setItem('lang', lang); } catch { /* ignore */ }

  const url = new URL(location.href);
  url.searchParams.set('lang', lang);
  history.replaceState(null, '', url); // the address can now be shared in this language
  document.querySelectorAll('a[href="api.html"], a[href^="api.html?"]').forEach(a => { a.href = `api.html?lang=${lang}`; });

  render();
  drawCharts();
}

// Looks up a text by key and fills in {placeholders}.
function t(key, values = {}) {
  const text = TEXT[lang][key] ?? TEXT.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => values[name]);
}

// Translates a value that comes from the data, such as a status code or an outcome.
const label = value => TEXT[lang].labels[value] ?? TEXT.en.labels[value] ?? value;

const locale = () => (lang === 'tr' ? 'tr-TR' : 'en-GB');

const format = {
  num: (n, digits = 1) => Number(n).toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }),
  count: n => Math.round(n).toLocaleString(locale()),
  pct: (n, digits = 1) => {
    const number = format.num(n, digits);
    return lang === 'tr' ? `%${number}` : `${number}%`; // Turkish puts the % sign first
  },
  wholePct: n => (lang === 'tr' ? `%${Math.round(n)}` : `${Math.round(n)}%`),
  seconds: n => t('unit.seconds', { n: format.num(n, 0) }),
  minutes: n => t('unit.minutes', { n: format.num(n, 0) }),
  time: d => d.toLocaleTimeString(locale(), { hour: '2-digit', minute: '2-digit' }),
  dayMonthTime: d => d.toLocaleString(locale(), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }),
  date: d => d.toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' }),
};

// SQL timestamps are Türkiye local time without an offset; read them as local wall-clock time.
const parseTs = value => new Date(String(value).replace(' ', 'T'));

/* ---------- Page text and tables ---------- */

function render() {
  document.documentElement.lang = lang;
  document.title = t('meta.title');

  document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
  // Only our own texts from i18n.js go through innerHTML, never values from the data.
  document.querySelectorAll('[data-i18n-html]').forEach(node => { node.innerHTML = t(node.dataset.i18nHtml); });
  document.querySelectorAll('[data-i18n-aria]').forEach(node => { node.setAttribute('aria-label', t(node.dataset.i18nAria)); });
  document.querySelectorAll('[data-i18n-alt]').forEach(node => { node.setAttribute('alt', t(node.dataset.i18nAlt)); });
  document.querySelectorAll('[data-lang]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.lang === lang));
  });

  fillKpis();
  fillScorecard();
  fillApprovalStats();
  fillInvoiceStats();
  fillExceptions();
  fillIncidents();
  fillOutcomes();
  fillSubmissions();
  fillTimeline();
  fillWireframes();
  fillQueryPanels();
}

const rows = name => results[name].rows;
const goal = id => rows('kpi_scorecard').find(r => r.goal === id);
const metric = n => rows('kpi_decision_time').find(r => r.n === n).value;
const sum = (list, key) => list.reduce((total, r) => total + (Number(r[key]) || 0), 0);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // textContent, never innerHTML
  return node;
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function headRow(keys, numeric = []) {
  const tr = el('tr');
  keys.forEach((key, i) => tr.append(el('th', numeric.includes(i) ? 'num' : null, t(key))));
  const thead = el('thead');
  thead.append(tr);
  return thead;
}

function cell(text, className, dataLabel) {
  const td = el('td', className, text);
  if (dataLabel) td.dataset.label = t(dataLabel); // shown as the row label on phones
  return td;
}

function fillKpis() {
  const adoption = rows('kpi_channel_adoption');
  setText('kpi-integrated', format.pct(adoption.at(-1).integrated_share_pct));
  setText('kpi-integrated-note', t('kpi.integratedNote', { w1: format.pct(adoption[0].integrated_share_pct) }));
  setText('kpi-decision', format.seconds(metric(3)));
  setText('kpi-invoice', format.pct(goal('G5').value_1));
  setText('kpi-lost', format.count(sum(rows('ops_incidents'), 'not_processed')));
}

function scoreResult(r) {
  const v = r.value_1;
  const v2 = r.value_2;
  switch (r.goal) {
    case 'G1': return t('score.G1.result', { v: format.pct(v) });
    case 'G2': return t('score.G2.result', { v: format.pct(v, 2), v2: format.pct(v2, 2) });
    case 'G3': return t('score.G3.result', { v: format.seconds(v), v2: format.pct(v2) });
    case 'G4': return t('score.G4.result', { v: format.num(v) });
    case 'G5': return t('score.G5.result', { v: format.pct(v), m: format.minutes(v2 * 60) });
    default: return t('score.G6.result', { v: format.count(v) });
  }
}

const BADGE = { MET: 'met', PARTLY_MET: 'partly', ON_TRACK: 'partly', NOT_MET: 'not-met' };

function fillScorecard() {
  const table = document.getElementById('scorecard');
  table.classList.add('stack');
  const tbody = el('tbody');
  for (const r of rows('kpi_scorecard')) {
    const tr = el('tr');
    tr.append(cell(r.goal));
    const what = el('td');
    what.append(el('span', 'goal-metric', t(`score.${r.goal}.metric`)), el('span', 'goal-target', t(`score.${r.goal}.target`)));
    tr.append(what);
    tr.append(cell(scoreResult(r), 'result', 'score.colResult'));
    tr.append(cell(t(`score.${r.goal}.baseline`), 'muted', 'score.colBaseline'));
    const status = el('td');
    status.append(el('span', `badge ${BADGE[r.status_code]}`, label(r.status_code)));
    tr.append(status);
    tbody.append(tr);
  }
  table.replaceChildren(headRow(['score.colGoal', 'score.colMetric', 'score.colResult', 'score.colBaseline', 'score.colStatus']), tbody);
}

function statList(id, items) {
  const dl = document.getElementById(id);
  dl.replaceChildren(...items.map(([key, value, note]) => {
    const box = el('div', 'stat');
    box.append(el('dt', null, t(key)), el('dd', null, value));
    if (note) box.append(el('dd', 'stat-note', note));
    return box;
  }));
}

function fillApprovalStats() {
  statList('approve-stats', [
    ['stat.median', format.seconds(metric(2))],
    ['stat.p95', format.seconds(metric(3))],
    ['stat.onTime', format.pct(metric(8))],
    ['stat.escalated', format.count(metric(9)), t('stat.escalatedNote', { n: format.count(metric(7)) })],
  ]);
}

function fillInvoiceStats() {
  const weeks = rows('kpi_invoice_cycle');
  const notified = weeks.reduce((total, w) => total + w.notified_within_1h_pct * w.webhook_notifications, 0)
    / sum(weeks, 'webhook_notifications');
  const months = rows('kpi_reconciliation');
  statList('invoice-stats', [
    ['stat.sameDay', format.pct(goal('G5').value_1), t('stat.sameDayNote')],
    ['stat.toInbox', format.minutes(goal('G5').value_2 * 60)],
    ['stat.notified', format.pct(notified), t('stat.notifiedNote')],
    ['stat.mismatches', format.count(sum(months, 'mismatches')), t('stat.mismatchesNote', { n: format.count(sum(months, 'acknowledged')) })],
  ]);
}

function fillExceptions() {
  const table = document.getElementById('exceptions');
  table.classList.add('stack');
  const tbody = el('tbody');
  const all = rows('daily_exception_report');
  const groups = [...new Set(all.map(r => r.exception_group.charAt(0)))];
  for (const g of groups) {
    const items = all.filter(r => r.exception_group.charAt(0) === g);
    const head = el('tr', 'group-row');
    const td = el('td', null, `${g}  ${t(`group.${g}`)}`);
    td.colSpan = 5;
    td.append(el('span', 'count', items.length === 1 ? t('exc.item') : t('exc.items', { n: items.length })));
    head.append(td);
    tbody.append(head);
    for (const r of items) {
      const tr = el('tr');
      const reference = ['2', '3'].includes(g) ? r.document_no : r.reference;
      tr.append(cell(reference, 'ref'));
      tr.append(cell(r.dealer_code, 'ref', 'exc.colDealer'));
      tr.append(cell(t(`issue.${r.issue_code}`, { doc: r.document_no, n: r.quantity })));
      tr.append(cell(format.dayMonthTime(parseTs(r.since)), 'muted', 'exc.colSince'));
      tr.append(cell(t('unit.hours', { n: format.count(r.age_hours) }), 'num', 'exc.colAge'));
      tbody.append(tr);
    }
  }
  table.replaceChildren(headRow(['exc.colReference', 'exc.colDealer', 'exc.colIssue', 'exc.colSince', 'exc.colAge'], [4]), tbody);
}

function fillIncidents() {
  const table = document.getElementById('incidents');
  table.classList.add('stack');
  const tbody = el('tbody');
  for (const r of rows('ops_incidents')) {
    const start = parseTs(r.started_at);
    const end = parseTs(r.ended_at);
    const tr = el('tr');
    const id = el('td');
    id.append(el('span', 'ref', r.incident_id), el('span', 'cell-sub', t(`incident.${r.incident_id}`)));
    tr.append(id);
    tr.append(cell(label(r.system), null, 'inc.colSystem'));
    tr.append(cell(t('inc.window', { date: format.date(start), start: format.time(start), end: format.time(end) }), 'muted', 'inc.colWhen'));
    tr.append(cell(format.minutes(r.duration_minutes), 'num', 'inc.colDuration'));
    tr.append(cell(t(`inc.affected.${r.system}`, { n: format.count(r.affected) }), null, 'inc.colAffected'));
    tr.append(cell(format.minutes(r.longest_delay_minutes), 'num', 'inc.colWait'));
    tr.append(cell(format.count(r.not_processed), 'num', 'inc.colLost'));
    tbody.append(tr);
  }
  table.replaceChildren(headRow(['inc.colIncident', 'inc.colSystem', 'inc.colWhen', 'inc.colDuration',
    'inc.colAffected', 'inc.colWait', 'inc.colLost'], [3, 5, 6]), tbody);
}

function fillOutcomes() {
  const data = rows('ops_invoice_delivery');
  const first = data.find(r => r.outcome === 'Delivered first time');
  setText('outcomes-note', t('res.outcomesNote', {
    total: format.count(sum(data, 'invoices')),
    first: format.count(first ? first.invoices : 0),
    day5: format.count(sum(data, 'reached_day5_alert')),
  }));
  const tbody = el('tbody');
  for (const r of data) {
    const tr = el('tr');
    tr.append(cell(label(r.outcome)));
    tr.append(cell(format.count(r.invoices), 'num'));
    tr.append(cell(format.pct(r.share_pct, 2), 'num'));
    tr.append(cell(r.median_hours_to_inbox === null ? t('na') : format.num(r.median_hours_to_inbox, 2), 'num'));
    tr.append(cell(format.count(r.reached_day5_alert), 'num'));
    tr.append(cell(format.count(r.beyond_7_day_limit), 'num'));
    tbody.append(tr);
  }
  document.getElementById('outcomes').replaceChildren(
    headRow(['out.colPath', 'out.colInvoices', 'out.colShare', 'out.colMedian', 'out.colDay5', 'out.colOver7'], [1, 2, 3, 4, 5]), tbody);
}

function fillSubmissions() {
  const data = rows('ops_order_submissions');
  const refused = data.filter(r => r.http_status !== 202);
  const byCode = {};
  refused.forEach(r => {
    const code = r.field_error_code || r.result_code;
    byCode[code] = (byCode[code] ?? 0) + r.submissions;
  });
  const top = Object.entries(byCode).sort((a, b) => b[1] - a[1])[0][0];
  setText('submissions-note', t('res.submissionsNote', {
    replayed: format.count(sum(data.filter(r => r.result_code === 'REPLAYED'), 'submissions')),
    failed: format.count(sum(refused, 'submissions')),
    top: `${t(`code.${top}`)} (${top})`,
  }));
}

function fillTimeline() {
  const points = Object.fromEntries(plan.sprints.map(s => [`s${s.sprint}`, s.points]));
  document.getElementById('timeline').replaceChildren(...TIMELINE.map(step => {
    const li = el('li', points[step] === undefined ? 'milestone' : null);
    li.append(el('span', 'step', t(`plan.${step}`)), el('span', 'dates', t(`plan.${step}Dates`)),
      el('span', 'goal', t(`plan.${step}Goal`)),
      el('span', 'points', points[step] === undefined ? '' : t('unit.points', { n: points[step] })));
    return li;
  }));
}

function fillWireframes() {
  document.getElementById('wireframes').replaceChildren(...WIREFRAMES.map(name => {
    const figure = el('figure');
    const link = el('a');
    link.href = `assets/wireframes/${name}.png`;
    const img = el('img');
    img.src = `assets/wireframes/${name}.png`;
    img.alt = t(`wf.${name}`);
    img.loading = 'lazy';
    link.append(img);
    figure.append(link, el('figcaption', null, t(`wf.${name}`)));
    return figure;
  }));
}

function fillQueryPanels() {
  document.querySelectorAll('details[data-query]').forEach(details => {
    const query = results[details.dataset.query];

    const source = el('p', 'query-file', t('query.source'));
    const link = el('a', null, query.file);
    link.href = REPO_FILES + query.file;
    source.append(link);

    const pre = el('pre');
    pre.append(el('code', null, query.sql));

    // replaceChildren keeps the panel open or closed as the visitor left it.
    details.replaceChildren(el('summary', null, `${t('query.summary')}: ${query.file.split('/').pop()}`), source, pre, resultTable(query));
  });
}

// The SQL result as a plain table. Column names stay as they are in SQL.
function resultTable(query) {
  const columns = query.columns;
  const head = el('tr');
  columns.forEach(c => head.append(el('th', null, c)));
  const thead = el('thead');
  thead.append(head);

  const tbody = el('tbody');
  for (const row of query.rows) {
    const tr = el('tr');
    columns.forEach(c => {
      const value = row[c];
      tr.append(el('td', null, value === null ? 'NULL' : typeof value === 'number' ? value.toLocaleString(locale()) : String(value)));
    });
    tbody.append(tr);
  }

  const table = el('table');
  table.append(thead, tbody);
  const wrap = el('div', 'query-table');
  wrap.append(table);
  return wrap;
}

/* ---------- Charts ---------- */

const cssVar = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Draws each bar's value just past its end, in the text color (never the bar color).
const valueLabels = {
  id: 'valueLabels',
  afterDatasetsDraw(chart, _args, options) {
    if (!options.format) return;
    const { ctx } = chart;
    const horizontal = chart.options.indexAxis === 'y';
    ctx.save();
    ctx.font = `500 12px ${FONT}`;
    ctx.fillStyle = cssVar('--text-secondary');
    ctx.textAlign = horizontal ? 'left' : 'center';
    ctx.textBaseline = horizontal ? 'middle' : 'bottom';
    chart.getDatasetMeta(0).data.forEach((bar, j) => {
      const text = options.format(chart.data.datasets[0].data[j]);
      if (horizontal) ctx.fillText(text, bar.x + 6, bar.y);
      else ctx.fillText(text, bar.x, bar.y - 6);
    });
    ctx.restore();
  },
};

function colors() {
  return {
    accent: cssVar('--accent'),
    accentHover: cssVar('--accent-hover'),
    context: cssVar('--context'),
    contextHover: cssVar('--context-hover'),
    exhausted: cssVar('--exhausted'),
    ink: cssVar('--ink'),
    text: cssVar('--text-secondary'),
    muted: cssVar('--muted'),
    grid: cssVar('--grid'),
    baseline: cssVar('--baseline'),
    raised: cssVar('--raised'),
    hairline: cssVar('--hairline'),
  };
}

function drawCharts() {
  charts.forEach(chart => chart.destroy());
  const c = colors();
  Chart.defaults.font.family = FONT;
  Chart.defaults.font.size = 13;
  Chart.defaults.color = c.muted;
  charts = [adoptionChart(c), phoneChart(c), stockApiChart(c), approvalsChart(c), webhookChart(c), epicsChart(c)];
}

function tooltip(c, { legend = false, label: labelFn, footer, title } = {}) {
  return {
    backgroundColor: c.raised,
    borderColor: c.hairline,
    borderWidth: 1,
    cornerRadius: 6,
    padding: 10,
    caretSize: 0,
    titleColor: c.muted,
    titleFont: { weight: '400', size: 12 },
    bodyColor: c.ink,
    bodyFont: { weight: '600', size: 14 },
    footerColor: c.muted,
    footerFont: { weight: '400', size: 12 },
    displayColors: legend,
    usePointStyle: true,
    callbacks: {
      ...(title ? { title } : {}),
      ...(labelFn ? { label: labelFn } : {}),
      ...(footer ? { footer } : {}),
      labelPointStyle: () => ({ pointStyle: 'rectRounded', rotation: 0 }),
    },
  };
}

function axes(c, { yMax, yStep, yFormat, xFormat, horizontal = false, stacked = false }) {
  const value = {
    min: 0,
    ...(yMax ? { max: yMax } : {}),
    stacked,
    ticks: { color: c.muted, ...(yStep ? { stepSize: yStep } : {}), ...(yFormat ? { callback: yFormat } : {}) },
    grid: { color: c.grid, drawTicks: false },
    border: { display: false },
  };
  const category = {
    stacked,
    ticks: { color: c.text, ...(xFormat ? { callback: xFormat } : {}), autoSkip: true, maxRotation: 0 },
    grid: { display: false },
    border: { color: c.baseline },
  };
  return horizontal ? { x: value, y: category } : { x: category, y: value };
}

const legendOptions = c => ({
  position: 'top',
  align: 'start',
  labels: { color: c.text, boxWidth: 12, boxHeight: 12, useBorderRadius: true, borderRadius: 2, padding: 16 },
});

const weekLabels = data => data.map((_, i) => t('chart.week', { n: i + 1 }));
const weekTitle = items => t('chart.weekLong', { n: items[0].dataIndex + 1 });

function targetLine(value, length, c) {
  return {
    type: 'line',
    label: t('chart.target'),
    data: Array(length).fill(value),
    borderColor: c.muted,
    borderWidth: 1.5,
    borderDash: [6, 4],
    pointRadius: 0,
    pointHoverRadius: 0,
    order: 0,
  };
}

const base = c => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  layout: { padding: { right: 8 } },
  datasets: { bar: { maxBarThickness: 28, borderRadius: 4, borderSkipped: 'start', barPercentage: 0.82 } },
  interaction: { mode: 'index', intersect: false },
});

function adoptionChart(c) {
  const data = rows('kpi_channel_adoption');
  return new Chart(document.getElementById('chart-adoption'), {
    type: 'bar',
    data: {
      labels: weekLabels(data),
      datasets: [
        { label: t('chart.share'), data: data.map(r => r.integrated_share_pct), backgroundColor: c.accent, hoverBackgroundColor: c.accentHover, order: 1 },
        targetLine(80, data.length, c),
      ],
    },
    options: {
      ...base(c),
      scales: axes(c, { yMax: 100, yStep: 20, yFormat: v => format.wholePct(v) }),
      plugins: {
        legend: { display: false },
        tooltip: tooltip(c, {
          title: weekTitle,
          label: ctx => `${ctx.dataset.label}: ${format.pct(ctx.parsed.y)}`,
          footer: items => t('chart.lines', { n: format.count(data[items[0].dataIndex].order_lines) }),
        }),
      },
    },
  });
}

function phoneChart(c) {
  const data = rows('kpi_stock_self_service');
  return new Chart(document.getElementById('chart-phone'), {
    type: 'bar',
    data: {
      labels: weekLabels(data),
      datasets: [
        { label: t('chart.calls'), data: data.map(r => r.phone_stock_questions_per_day), backgroundColor: c.accent, hoverBackgroundColor: c.accentHover, order: 1 },
        targetLine(6, data.length, c),
      ],
    },
    options: {
      ...base(c),
      scales: axes(c, { yMax: 70, yStep: 20 }),
      plugins: {
        legend: { display: false },
        tooltip: tooltip(c, { title: weekTitle, label: ctx => `${ctx.dataset.label}: ${format.num(ctx.parsed.y)}` }),
      },
    },
  });
}

function stockApiChart(c) {
  const data = rows('kpi_stock_self_service');
  return new Chart(document.getElementById('chart-stock-api'), {
    type: 'bar',
    data: {
      labels: weekLabels(data),
      datasets: [{ label: t('chart.queries'), data: data.map(r => r.stock_queries_per_day), backgroundColor: c.context, hoverBackgroundColor: c.contextHover }],
    },
    options: {
      ...base(c),
      scales: axes(c, { yFormat: v => format.count(v) }),
      plugins: {
        legend: { display: false },
        tooltip: tooltip(c, { title: weekTitle, label: ctx => `${ctx.dataset.label}: ${format.count(ctx.parsed.y)}` }),
      },
    },
  });
}

function approvalsChart(c) {
  const values = [metric(8), metric(11), metric(12)];
  return new Chart(document.getElementById('chart-approvals'), {
    type: 'bar',
    data: {
      labels: [t('chart.allTasks'), t('chart.credit'), t('chart.stock')],
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => (i === 1 ? c.accent : c.context)),
        hoverBackgroundColor: values.map((_, i) => (i === 1 ? c.accentHover : c.contextHover)),
      }],
    },
    options: {
      ...base(c),
      indexAxis: 'y',
      interaction: { mode: 'nearest', intersect: true },
      scales: axes(c, { yMax: 100, yStep: 25, yFormat: v => format.wholePct(v), horizontal: true }),
      plugins: {
        legend: { display: false },
        valueLabels: { format: v => format.pct(v) },
        tooltip: tooltip(c, { label: ctx => t('chart.onTime', { pct: format.pct(ctx.parsed.x) }) }),
      },
    },
    plugins: [valueLabels],
  });
}

function webhookChart(c) {
  const data = rows('ops_webhook_delivery');
  const first = data.map(r => Math.round(r.events * r.first_attempt_pct / 100));
  return new Chart(document.getElementById('chart-webhooks'), {
    type: 'bar',
    data: {
      labels: weekLabels(data),
      datasets: [
        { label: t('chart.firstAttempt'), data: first, backgroundColor: c.context, hoverBackgroundColor: c.contextHover },
        { label: t('chart.afterRetry'), data: data.map(r => r.delivered_after_retry), backgroundColor: c.accent, hoverBackgroundColor: c.accentHover },
        { label: t('chart.exhausted'), data: data.map(r => r.exhausted), backgroundColor: c.exhausted, hoverBackgroundColor: c.exhausted },
      ],
    },
    options: {
      ...base(c),
      datasets: { bar: { maxBarThickness: 28, borderRadius: 0, barPercentage: 0.82 } },
      scales: axes(c, { stacked: true, yFormat: v => format.count(v) }),
      plugins: {
        legend: legendOptions(c),
        tooltip: tooltip(c, {
          legend: true,
          title: weekTitle,
          label: ctx => `${ctx.dataset.label}: ${format.count(ctx.parsed.y)}`,
          footer: items => t('chart.events', { n: format.count(data[items[0].dataIndex].events) }),
        }),
      },
    },
  });
}

function epicsChart(c) {
  const epics = plan.epics;
  return new Chart(document.getElementById('chart-epics'), {
    type: 'bar',
    data: {
      labels: epics.map(e => `${e.id} ${label(e.name)}`),
      datasets: [{ data: epics.map(e => e.points), backgroundColor: c.accent, hoverBackgroundColor: c.accentHover }],
    },
    options: {
      ...base(c),
      indexAxis: 'y',
      interaction: { mode: 'nearest', intersect: true },
      scales: axes(c, { yMax: 40, yStep: 10, horizontal: true }),
      plugins: {
        legend: { display: false },
        valueLabels: { format: v => format.count(v) },
        tooltip: tooltip(c, { label: ctx => t('chart.points', { n: ctx.parsed.x, items: epics[ctx.dataIndex].items }) }),
      },
    },
    plugins: [valueLabels],
  });
}

/* ---------- Sequence and state diagrams (loaded on demand) ---------- */

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });
}

const prefersDark = () => {
  const forced = document.documentElement.dataset.theme;
  return forced ? forced === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
};

async function drawUml(force = false) {
  if (umlState === 'loading' || (umlState === 'done' && !force)) return;
  const box = document.getElementById('uml-diagrams');
  if (umlState !== 'done') box.replaceChildren(el('p', 'uml-status', t('uml.loading')));
  umlState = 'loading';
  try {
    if (!window.mermaid) await loadScript(MERMAID_URL);
    window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: prefersDark() ? 'dark' : 'neutral', fontFamily: FONT });
    const figures = [];
    for (const name of UML) {
      const source = await fetch(`assets/uml/${name}.mmd`).then(response => response.text());
      const { svg } = await window.mermaid.render(`uml-${name}-${Date.now()}`, source);
      const figure = el('figure');
      const caption = el('figcaption', null, t(`uml.${name}`));
      caption.dataset.i18n = `uml.${name}`; // keeps the caption in the chosen language
      const holder = el('div');
      holder.innerHTML = svg; // SVG drawn by Mermaid, with strict security, from this repository's own diagram files
      figure.append(caption, holder);
      figures.push(figure);
    }
    box.replaceChildren(...figures);
    umlState = 'done';
  } catch {
    umlState = 'idle';
    box.replaceChildren(el('p', 'uml-status', t('uml.error')));
  }
}
