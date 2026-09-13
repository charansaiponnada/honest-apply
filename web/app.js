// Honest Apply — agent app. Vanilla JS, no build step.
// All server/LLM/job-board text is inserted via textContent (see h()), never innerHTML.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const safeUrl = (u) => (typeof u === 'string' && /^https:\/\//.test(u) ? u : null);
const pct = (x) => `${Math.round((x || 0) * 100)}%`;

function detailText(detail, status) {
  if (!detail) return `HTTP ${status}`;
  return typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ');
}

async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(detailText(data.detail, res.status));
  return data;
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 4200);
}

async function withBusy(btn, label, fn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.replaceChildren(h('span', { class: 'spinner', 'aria-hidden': 'true' }), label);
  try { return await fn(); } finally { btn.disabled = false; btn.textContent = original; }
}

// ---------------------------------------------------------------- tabs
function showTab(name) {
  $$('.tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
  $$('[role=tabpanel]').forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  if (name === 'tracker') loadHistory();
  if (name === 'reliability') loadEvalSummary();
  history.replaceState(null, '', `#${name}`);
}
$$('.tab').forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));

// ---------------------------------------------------------------- status + chaos
let status = { google: false, faults: [], available_faults: [] };
const FAULT_LABELS = {
  gmail: 'Gmail down', crm: 'HubSpot down', calendar: 'Calendar down',
  slack: 'Slack down', llm_429: 'LLM rate-limited', google_auth: 'Google token expired',
};

async function loadStatus() {
  status = await api('/api/status');
  renderStatus();
  renderChaos();
}

function renderStatus() {
  const dot = (label, live, title) =>
    h('span', { title }, h('span', { class: `dot ${live ? 'live' : 'mock'}` }), `${label} · ${live ? 'live' : 'mock'}`);
  $('#status-row').replaceChildren(
    dot('LLM', status.llm, status.model),
    dot('Google', status.google, 'Gmail, Calendar'),
    dot('HubSpot', status.crm, 'CRM deals'),
    dot('Slack', status.slack, 'Incoming webhook'),
  );
  $('#thresholds').textContent =
    `Flag below ${pct(status.review_threshold)} overlap · send only at ${pct(status.send_threshold)}+ with every check clean.`;
  const allow = $('#allow-send');
  allow.disabled = !status.google;
  if (!status.google) allow.checked = false;
  $('#send-hint').textContent = status.google
    ? 'Sends only if a recipient is set, overlap clears the send bar and every receipt checks out.'
    : 'Connect Gmail to enable. Until then everything stays a draft.';
}

function renderChaos() {
  $('#chaos').replaceChildren(
    ...status.available_faults.map((name) =>
      h('label', {},
        h('input', {
          type: 'checkbox', checked: status.faults.includes(name),
          onchange: async (e) => {
            const next = new Set(status.faults);
            e.target.checked ? next.add(name) : next.delete(name);
            try {
              const res = await api('/api/faults', { method: 'POST', body: { faults: [...next] } });
              status.faults = res.faults;
            } catch (err) { toast(err.message); e.target.checked = !e.target.checked; }
            renderChaosBanner();
          },
        }),
        FAULT_LABELS[name] || name)),
  );
  renderChaosBanner();
}

function renderChaosBanner() {
  const b = $('#chaos-banner');
  b.hidden = !status.faults.length;
  b.textContent = `Chaos panel active: ${status.faults.map((f) => FAULT_LABELS[f] || f).join(', ')}`;
}

// ---------------------------------------------------------------- jobs
let jobPool = null;
$('#jobs').addEventListener('toggle', async (e) => {
  if (!e.target.open || jobPool) return;
  $('#jobs-hint').textContent = 'Loading live listings…';
  try {
    const data = await api('/api/jobs?limit=60');
    jobPool = data.jobs;
    $('#jobs-hint').textContent = data.error || 'Arbeitnow, Remotive and RemoteOK. Public APIs, no scraping.';
    renderJobs();
  } catch (err) { $('#jobs-hint').textContent = err.message; }
});
$('#jobs-filter').addEventListener('input', renderJobs);

function renderJobs() {
  if (!jobPool) return;
  const q = $('#jobs-filter').value.trim().toLowerCase();
  const matches = jobPool.filter((j) =>
    !q || `${j.title} ${j.company_name} ${j.location} ${(j.tags || []).join(' ')}`.toLowerCase().includes(q));
  $('#jobs-count').textContent = `${matches.length} listings`;
  $('#job-list').replaceChildren(
    ...matches.slice(0, 40).map((j) =>
      h('div', { class: 'job' },
        h('div', {},
          h('div', {}, h('strong', {}, j.title), ' — ', j.company_name),
          h('div', { class: 'job-meta' }, [j.source, j.location, j.posted].filter(Boolean).join(' · '))),
        h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => useJob(j) }, 'Use'))),
  );
}

// ---------------------------------------------------------------- run
let jdSource = 'pasted text';
$('#jd').addEventListener('input', () => (jdSource = 'pasted text'));

const AGENT_STATES = {
  running: ['is-running', 'Working…'],
  done: ['is-done', 'Done'],
  reviewing: ['is-running', 'Checking receipts + fit…'],
  acting: ['is-running', 'Acting in apps…'],
  drafted: ['is-done', 'Drafted, ready for you'],
  sent: ['is-done', 'Sent'],
  partial: ['is-warn', 'Partly failed, see actions'],
  flagged: ['is-warn', 'Flagged, nothing sent'],
  duplicate: ['is-warn', 'Duplicate, skipped'],
};

function resetPipeline() {
  $$('.agent').forEach((a) => {
    a.className = 'agent';
    a.querySelector('.agent-state').textContent = a.dataset.defaultState ||= a.querySelector('.agent-state').textContent;
  });
  $$('.app-chip').forEach((c) => (c.className = 'app-chip'));
  const trace = $('#trace');
  trace.replaceChildren();
  trace.hidden = false;
  $('#result').hidden = true;
  $('#error').hidden = true;
}

function trace(text, cls) {
  const t = $('#trace');
  t.append(h('div', { class: cls }, `${new Date().toLocaleTimeString()}  ${text}`));
  t.scrollTop = t.scrollHeight;
}

function handleEvent(ev) {
  if (ev.type === 'step') {
    const el = $(`.agent[data-agent="${ev.step}"]`);
    const [cls, label] = AGENT_STATES[ev.status] || ['', ev.status];
    el.className = `agent ${cls}`;
    el.querySelector('.agent-state').textContent = label;
    trace(`${ev.step}: ${ev.status}`);
  } else if (ev.type === 'tool') {
    const chip = $(`.app-chip[data-app="${ev.app}"]`);
    const cls = { running: 'is-running', ok: 'is-done', mocked: 'is-done', error: 'is-error' }[ev.status] || '';
    chip.className = `app-chip ${cls}`;
    if (ev.status !== 'running') trace(`${ev.app}: ${ev.status} — ${ev.detail}`, ev.status === 'error' ? 't-fault' : '');
  } else if (ev.type === 'github') {
    trace(ev.error ? `github: ${ev.error}` : `github: ${ev.verified.length ? `verified from your repos: ${ev.verified.join(', ')}` : 'no extra skills this job needs'}`);
  } else if (ev.type === 'fault') {
    trace(`chaos panel: injecting ${ev.names.join(', ')}`, 't-fault');
  } else if (ev.type === 'result') {
    $$('.app-chip').forEach((c) => { if (!c.className.includes('is-')) c.classList.add('is-skipped'); });
    renderResult(ev.result);
  } else if (ev.type === 'error') {
    showError(ev.detail);
  }
}

async function readStream(res, onEvent) {
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (chunk.startsWith('data: ')) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}

function showError(msg) {
  const e = $('#error');
  e.textContent = msg;
  e.hidden = false;
}

$('#run-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = $('#run-btn');
  resetPipeline();
  await withBusy(btn, 'Running…', async () => {
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_text: $('#resume').value,
          jd_text: $('#jd').value,
          company: $('#company').value,
          role: $('#role').value,
          recipient: $('#recipient').value,
          allow_send: $('#allow-send').checked,
          jd_source: jdSource,
          user_id: $('#user-id').value.trim(),
          slack_channel: $('#slack-channel').value.trim(),
          github_username: $('#github').value.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(detailText(data.detail, res.status));
      }
      await readStream(res, handleEvent);
    } catch (err) { showError(err.message); }
  });
});

// ---------------------------------------------------------------- result
const OUTCOMES = {
  sent: ['badge-success', 'Sent'],
  drafted: ['badge-neutral', 'Drafted, ready for you to send'],
  partial: ['badge-danger', 'Partly failed'],
  flagged: ['badge-warning', 'Flagged for review'],
  duplicate: ['badge-neutral', 'Duplicate, skipped'],
};
const APP_LABELS = { gmail: 'Gmail', calendar: 'Calendar', crm: 'HubSpot', slack: 'Slack' };

function renderResult(r) {
  const [badgeCls, badgeText] = OUTCOMES[r.outcome] || ['badge-neutral', r.outcome];
  const verdict = r.executor_verdict;
  const undoBtn = h('button', {
    class: 'btn btn-ghost btn-sm', type: 'button', hidden: !['sent', 'drafted', 'partial'].includes(r.outcome),
    onclick: (e) => undoRun(r.run_id, e.currentTarget),
  }, 'Undo everything');

  const panels = {
    Receipts: renderReceipts(r),
    'Cover note': h('div', { class: 'prose' }, r.cover_note || '—'),
    Gaps: renderGaps(r.gap_report),
    Actions: renderActions(r.actions),
    Requirements: renderRequirements(r.requirements),
  };
  const body = h('div');
  const subtabs = h('div', { class: 'subtabs', role: 'tablist' },
    Object.keys(panels).map((name, i) =>
      h('button', {
        class: 'subtab', role: 'tab', type: 'button', 'aria-selected': String(i === 0),
        onclick: (e) => {
          $$('.subtab', subtabs).forEach((b) => b.setAttribute('aria-selected', String(b === e.currentTarget)));
          body.replaceChildren(panels[name]);
        },
      }, name === 'Gaps' && gapCount(r.gap_report) ? `Gaps (${gapCount(r.gap_report)})` : name)));
  body.append(panels.Receipts);

  const callouts = [];
  if (r.outcome === 'flagged') {
    callouts.push(h('div', { class: 'callout' },
      r.gap_report.seniority ? `${r.gap_report.seniority}, so nothing was sent. Slack was told why.`
      : verdict.faithful
        ? `Overlap ${pct(r.guardrail.score)} is below the ${pct(r.guardrail.threshold)} bar, so Gmail, Calendar and HubSpot were skipped. Slack was told why.`
        : `The receipts check found ${verdict.unsupported_claims.length} claim(s) your resume doesn't back up, so nothing was sent anywhere.`));
  } else if (r.outcome === 'duplicate') {
    callouts.push(h('div', { class: 'callout' }, `You already applied to ${r.role} at ${r.company}. Undo that run from the Tracker to apply again.`));
  } else if (r.outcome === 'partial') {
    callouts.push(h('div', { class: 'callout danger' }, 'Some apps failed after retries (see Actions). The rest completed; re-run to retry.'));
  }

  $('#result').replaceChildren(
    h('div', { class: 'result-head' },
      h('span', { class: `badge ${badgeCls}` }, badgeText),
      h('span', { class: 'meta' },
        `${r.role} @ ${r.company} · overlap ${pct(r.guardrail.score)} · Executor ${r.executor_mode} · `,
        r.used_live_llm ? 'live LLM' : 'rule-based fallback'),
      h('span', { style: 'margin-left:auto' }, undoBtn)),
    h('p', { class: 'meta', style: 'margin:.2rem 0 .6rem' },
      `Executor review: ${verdict.recommendation} (${pct(verdict.confidence)}) — ${verdict.reason}`),
    ...callouts,
    subtabs,
    body,
  );
  $('#result').hidden = false;
  $('#result').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
}

function renderReceipts(r) {
  const receipts = r.executor_verdict.receipts || [];
  const original = h('div', { class: 'lines' },
    r.resume_lines.map((line, i) => h('div', { class: 'line', id: `src-${i}` }, h('span', { class: 'line-num' }, i), h('span', {}, line))));
  const focus = (idx) => {
    $$('.line.highlight', original).forEach((l) => l.classList.remove('highlight'));
    if (idx == null) return;
    const target = $(`#src-${idx}`, original);
    if (target) { target.classList.add('highlight'); target.scrollIntoView({ block: 'nearest' }); }
  };
  const tailored = h('div', { class: 'lines' },
    receipts.map((rc) =>
      h('div', {
        class: `line tailored${rc.supported ? '' : ' unsupported'}`, tabindex: '0',
        onmouseenter: () => focus(rc.source_line), onfocus: () => focus(rc.source_line), onclick: () => focus(rc.source_line),
      },
      h('span', { class: 'line-num' }, rc.source_line ?? '?'),
      h('span', {}, rc.tailored, rc.reason ? h('span', { class: 'line-reason' }, rc.reason) : null))));
  const unsupported = receipts.filter((rc) => !rc.supported).length;
  return h('div', {},
    h('p', { class: 'hint', style: 'margin-top:0' },
      unsupported
        ? `${unsupported} line(s) failed the receipts check. They are outlined below.`
        : `All ${receipts.length} tailored lines trace back to your original resume. Hover a line to see its source.`),
    h('div', { class: 'receipts' },
      h('div', {}, h('span', { class: 'label' }, 'Tailored (source line →)'), tailored),
      h('div', {}, h('span', { class: 'label' }, 'Your original resume'), original)));
}

const gapCount = (g) => (g ? g.missing_must_haves.length + g.missing_keywords.length + g.unsupported_claims.length + (g.seniority ? 1 : 0) : 0);

function renderGaps(g) {
  if (!gapCount(g)) return h('div', { class: 'empty' }, 'No gaps: your resume covers what this job asks for.');
  const section = (title, items, cls) => items.length
    ? h('div', { style: 'margin-bottom:1rem' }, h('span', { class: 'label' }, title), h('div', { class: 'chips' }, items.map((i) => h('span', { class: `chip ${cls}` }, i))))
    : null;
  return h('div', {},
    h('p', { class: 'hint', style: 'margin-top:0' }, "What this job wants that your resume doesn't show. Worth learning, or worth skipping this one."),
    g.seniority ? h('div', { class: 'callout' }, g.seniority) : null,
    section('Must-haves not found', g.missing_must_haves, 'gap'),
    section('Keywords not found', g.missing_keywords, 'gap'),
    g.unsupported_claims.length
      ? h('div', {}, h('span', { class: 'label' }, 'Blocked claims'), h('ul', { class: 'list-plain' }, g.unsupported_claims.map((c) => h('li', {}, c))))
      : null);
}

function actionRow(key, a) {
  const ok = ['ok', 'mocked'].includes(a.status);
  const icon = a.status === 'skipped' ? ['skip', '–'] : ok ? ['ok', '✓'] : ['err', '✕'];
  const link = safeUrl(a.link);
  return h('div', { class: 'action-row' },
    h('span', { class: `status-icon ${icon[0]}`, 'aria-hidden': 'true' }, icon[1]),
    h('div', {},
      h('strong', {}, APP_LABELS[key] || key), a.status === 'mocked' ? h('span', { class: 'meta' }, ' (mock)') : null,
      h('div', { class: 'meta' }, a.detail),
      link ? h('a', { href: link, target: '_blank', rel: 'noopener' }, `Open in ${APP_LABELS[key] || key} ↗`) : null));
}

function renderActions(actions) {
  const keys = Object.keys(actions);
  if (!keys.length) return h('div', { class: 'empty' }, 'No app actions ran.');
  return h('div', {},
    h('p', { class: 'hint', style: 'margin-top:0' }, 'Run in order and chained: the email link goes into the reminder, both links go onto the CRM deal, Slack gets all three.'),
    keys.map((k) => actionRow(k, actions[k])));
}

function renderRequirements(req) {
  const chips = (items) => h('div', { class: 'chips' }, (items || []).map((i) => h('span', { class: 'chip' }, i)));
  return h('div', { class: 'two-col' },
    h('div', {},
      h('span', { class: 'label' }, 'Seniority'), h('p', { style: 'margin-top:0' }, req.seniority || '?'),
      h('span', { class: 'label' }, 'Skills'), chips(req.skills)),
    h('div', {},
      h('span', { class: 'label' }, 'Must-haves'), h('ul', { class: 'list-plain' }, (req.must_haves || []).map((m) => h('li', {}, m))),
      h('span', { class: 'label', style: 'margin-top:1rem' }, 'Keywords'), chips(req.keywords)));
}

async function undoRun(runId, btn) {
  await withBusy(btn, 'Undoing…', async () => {
    try {
      const res = await api(`/api/undo/${encodeURIComponent(runId)}`, { method: 'POST' });
      const summary = Object.entries(res.results).map(([k, v]) => `${APP_LABELS[k] || k}: ${v.status}`).join(' · ');
      toast(res.already_undone ? 'Already undone.' : `Undone. ${summary}`);
      btn.hidden = true;
      if (!$('#tab-tracker').hidden) loadHistory();
    } catch (err) { toast(err.message); }
  });
}

// ---------------------------------------------------------------- tracker
let historyRows = [];
async function loadHistory() {
  try { historyRows = await api('/api/history'); } catch (err) { toast(err.message); return; }
  const count = (fn) => historyRows.filter(fn).length;
  const live = (r) => !r.undone;
  $('#metrics').replaceChildren(
    ...[
      ['Applications', count(live)],
      ['Drafted or sent', count((r) => live(r) && ['drafted', 'sent'].includes(r.outcome))],
      ['Flagged', count((r) => r.outcome === 'flagged')],
      ['Replies', count((r) => live(r) && r.replied)],
    ].map(([label, value]) => h('div', { class: 'metric' }, h('div', { class: 'metric-value' }, value), h('div', { class: 'metric-label' }, label))),
  );
  renderHistory();
}
$('#history-filter').addEventListener('input', renderHistory);

function renderHistory() {
  const q = $('#history-filter').value.trim().toLowerCase();
  const rows = historyRows.filter((r) => !q || `${r.company} ${r.role}`.toLowerCase().includes(q));
  if (!rows.length) {
    $('#history').replaceChildren(h('div', { class: 'empty' }, historyRows.length ? 'No matches.' : 'No applications yet. Run the agent to start tracking.'));
    return;
  }
  const stateBadge = (r) => {
    if (r.undone) return h('span', { class: 'badge badge-neutral' }, 'Undone');
    if (r.replied) return h('span', { class: 'badge badge-success' }, 'Replied');
    const [cls, text] = OUTCOMES[r.outcome] || ['badge-neutral', r.outcome];
    return h('span', { class: `badge ${cls}` }, text.split(',')[0]);
  };
  $('#history').replaceChildren(h('div', { class: 'table-wrap' }, h('table', {},
    h('thead', {}, h('tr', {}, ['When', 'Company', 'Role', 'Overlap', 'Status', 'Executor', ''].map((t) => h('th', {}, t)))),
    h('tbody', {}, rows.map((r) => {
      const actionable = !r.undone && ['sent', 'drafted', 'partial'].includes(r.outcome);
      const replyLink = safeUrl(r.reply_link);
      return h('tr', {},
        h('td', {}, (r.started_at || '').replace('T', ' ').slice(0, 16)),
        h('td', {}, r.company), h('td', {}, r.role), h('td', {}, pct(r.overlap)),
        h('td', {}, stateBadge(r), replyLink ? h('a', { href: replyLink, target: '_blank', rel: 'noopener', style: 'margin-left:.4rem' }, 'reply ↗') : null),
        h('td', { class: 'meta' }, r.executor_mode || '—', r.faults?.length ? ' · chaos' : ''),
        h('td', { class: 'actions-cell' },
          actionable ? h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: (e) => undoRun(r.run_id, e.currentTarget) }, 'Undo') : null,
          actionable && !status.google && !r.replied && r.outcome !== 'partial'
            ? h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: (e) => simulateReply(r.run_id, e.currentTarget) }, 'Simulate reply')
            : null));
    })))));
}

function replySummary(res) {
  if (!res.replies.length) return `Checked ${res.checked} application(s) in ${res.mode} mode. No new replies.`;
  return res.replies.map((r) => (r.error ? `Error: ${r.error}` : `Reply from ${r.company}: CRM deal moved to replied, reminder cancelled, Slack pinged.`)).join(' ');
}

async function simulateReply(runId, btn) {
  await withBusy(btn, '…', async () => {
    try { toast(replySummary(await api(`/api/replies/simulate/${encodeURIComponent(runId)}`, { method: 'POST' }))); loadHistory(); }
    catch (err) { toast(err.message); }
  });
}

$('#sync-replies').addEventListener('click', (e) =>
  withBusy(e.currentTarget, 'Checking Gmail…', async () => {
    try { toast(replySummary(await api('/api/replies/sync', { method: 'POST' }))); loadHistory(); }
    catch (err) { toast(err.message); }
  }));

// ---------------------------------------------------------------- reliability
const CRITERIA = ['extraction', 'faithfulness', 'decision', 'actions'];

function renderSummary(title, s) {
  if (!s) return h('div', { class: 'card' }, h('h2', { class: 'section' }, title), h('p', { class: 'hint' }, 'Not run yet.'));
  const mark = (ok) => h('span', { class: ok ? 'pass' : 'fail' }, ok ? 'pass' : 'FAIL');
  return h('div', { class: 'card' },
    h('div', { class: 'result-head' },
      h('h2', { class: 'section', style: 'margin:0' }, title),
      h('span', { class: `badge ${s.passed === s.total ? 'badge-success' : 'badge-warning'}` }, `${s.passed}/${s.total} passed`),
      h('span', { class: 'meta' }, `${s.ran_at.replace('T', ' ')}${s.faults.length ? ` · faults: ${s.faults.join(', ')}` : ''}`)),
    h('div', { class: 'metrics' }, CRITERIA.map((c) =>
      h('div', { class: 'metric' }, h('div', { class: 'metric-value' }, `${s.criteria[c]}/${s.total}`), h('div', { class: 'metric-label' }, c)))),
    h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, ['Job description', 'Outcome', 'Overlap', ...CRITERIA, 'Result'].map((t) => h('th', {}, t)))),
      h('tbody', {}, s.rows.map((r) => h('tr', {},
        h('td', {}, r.jd_file),
        h('td', {}, r.error ? `crash: ${r.error}` : r.outcome),
        h('td', {}, r.error ? '—' : pct(r.overlap)),
        ...CRITERIA.map((c) => h('td', {}, mark(r[c]))),
        h('td', {}, mark(r.passed))))))));
}

async function loadEvalSummary() {
  try {
    const s = await api('/api/eval/summary');
    $('#eval-results').replaceChildren(renderSummary('Normal run', s.normal), h('div', { style: 'height:1rem' }), renderSummary('Under injected failures', s.faults));
  } catch (err) { toast(err.message); }
}

async function runEval(btn, faults) {
  await withBusy(btn, 'Running 10 job descriptions…', async () => {
    try { await api('/api/eval', { method: 'POST', body: { faults } }); await loadEvalSummary(); }
    catch (err) { toast(err.message); }
  });
}
$('#eval-normal').addEventListener('click', (e) => runEval(e.currentTarget, []));
$('#eval-faults').addEventListener('click', (e) => runEval(e.currentTarget, ['gmail', 'llm_429']));

// ---------------------------------------------------------------- connections (Composio)
const CONNECT_APPS = { gmail: 'Gmail', calendar: 'Google Calendar', crm: 'HubSpot', slack: 'Slack' };
const USER_ID_RE = /^[\w.@+-]{1,200}$/;
const store = {
  get: (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: still works for this visit */ } },
};

async function loadConnections() {
  const userId = $('#user-id').value.trim();
  store.set('userId', userId);
  store.set('slackChannel', $('#slack-channel').value.trim());
  let res;
  try { res = await api(`/api/connections?user_id=${encodeURIComponent(userId)}`); }
  catch (err) { $('#connections-hint').textContent = err.message; return; }

  const valid = USER_ID_RE.test(userId);
  $('#connections').replaceChildren(...Object.entries(CONNECT_APPS).map(([key, label]) => {
    const app = res.apps[key];
    const state = app.via === 'composio' ? 'Connected' : app.via === 'env' ? 'Server keys' : 'Not connected';
    return h('div', { class: 'conn-row' },
      h('span', { class: `dot ${app.connected ? 'live' : 'mock'}`, 'aria-hidden': 'true' }),
      h('span', { class: 'conn-name' }, label),
      h('span', { class: 'meta conn-state' }, state),
      res.composio && app.via !== 'composio'
        ? h('button', { class: 'btn btn-ghost btn-sm', type: 'button', disabled: !valid, onclick: (e) => connectApp(key, e.currentTarget) }, 'Connect')
        : null);
  }));
  $('#connections-hint').textContent = !res.composio
    ? 'One-click Connect needs COMPOSIO_API_KEY on the server. Using server keys where set, mock otherwise.'
    : valid ? 'Actions run on the accounts you connect. Composio stores the sign-in, not us.'
      : 'Enter your email, then connect your own apps.';

  status.google = res.apps.gmail.connected;
  status.crm = res.apps.crm.connected;
  status.slack = res.apps.slack.connected;
  renderStatus();
}

async function connectApp(key, btn) {
  await withBusy(btn, '…', async () => {
    try {
      const { redirect_url: url } = await api(`/api/connections/${key}/link`, { method: 'POST', body: { user_id: $('#user-id').value.trim() } });
      if (safeUrl(url)) location.href = url;
      else toast('Composio did not return a connect link.');
    } catch (err) { toast(err.message); }
  });
}

let connectionsTimer;
['#user-id', '#slack-channel'].forEach((sel) => $(sel).addEventListener('input', () => {
  clearTimeout(connectionsTimer);
  connectionsTimer = setTimeout(loadConnections, 500);
}));

// ---------------------------------------------------------------- resume upload + GitHub
function useJob(j) {
  $('#jd').value = j.description || j.title;
  $('#company').value = j.company_name || '';
  $('#role').value = j.title || '';
  jdSource = j.url || j.source;
  $('#jobs').open = false;
  toast(`Loaded ${j.title} at ${j.company_name}`);
}

$('#resume-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { toast('Resume file is over 5 MB.'); return; }
  try {
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
      reader.onerror = () => reject(new Error('Could not read that file.'));
      reader.readAsDataURL(file);
    });
    const res = await api('/api/resume/parse', { method: 'POST', body: { filename: file.name, data_base64: data } });
    $('#resume').value = res.text;
    toast(`Loaded ${file.name}`);
  } catch (err) { toast(err.message); }
});

let githubTimer;
$('#github').addEventListener('input', () => { clearTimeout(githubTimer); githubTimer = setTimeout(checkGithub, 600); });

async function checkGithub() {
  const username = $('#github').value.trim();
  store.set('github', username);
  const hint = $('#github-hint');
  if (!username) { hint.textContent = 'Skills your public repos prove get added, with the repo as the receipt.'; return; }
  if (!/^[A-Za-z0-9-]{1,39}$/.test(username)) { hint.textContent = 'Not a valid GitHub username.'; return; }
  try {
    const p = await api(`/api/github/${encodeURIComponent(username)}`);
    hint.textContent = p.error || `${p.repo_count} public repos · ${p.skills.slice(0, 6).join(', ') || 'no languages found'}`;
  } catch (err) { hint.textContent = err.message; }
}

// ---------------------------------------------------------------- recommendations + batch apply
let recJobs = [];
const batchResults = {};

$('#recs-btn').addEventListener('click', (e) => withBusy(e.currentTarget, 'Matching…', async () => {
  try {
    const res = await api('/api/recommendations', {
      method: 'POST',
      body: { resume_text: $('#resume').value, github_username: $('#github').value.trim(), limit: 10 },
    });
    recJobs = res.jobs;
    $('#recs-hint').textContent = recJobs.length
      ? `Top ${recJobs.length} of ${res.pool_size} live listings.${res.github_error ? ` GitHub: ${res.github_error}` : ''}`
      : (res.error || 'No live listings mention your skills right now.');
    renderRecs();
  } catch (err) { toast(err.message); }
}));

function renderRecs() {
  $('#recs').replaceChildren(...recJobs.map((j, i) =>
    h('label', { class: 'rec' },
      h('input', { type: 'checkbox', 'data-i': String(i), checked: i < 3 && !j.senior_role, onchange: updateBatchButton }),
      h('div', { class: 'rec-body' },
        h('div', {}, h('strong', {}, j.title), ' — ', j.company_name,
          j.senior_role ? h('span', { class: 'badge badge-warning', style: 'margin-left:.4rem' }, 'senior role') : null),
        h('div', { class: 'job-meta' },
          `Matches ${j.matched_skills.length} resume skills: ${j.matched_skills.slice(0, 6).join(', ') || '—'}`,
          j.github_skills.length ? ` · from GitHub: ${j.github_skills.slice(0, 4).join(', ')}` : '')),
      h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: (e) => { e.preventDefault(); useJob(j); } }, 'Use'))));
  updateBatchButton();
}

const selectedJobs = () => $$('#recs input[type=checkbox]').filter((c) => c.checked).map((c) => recJobs[Number(c.dataset.i)]);

function updateBatchButton() {
  const n = selectedJobs().length;
  const btn = $('#batch-btn');
  btn.disabled = n === 0 || n > 5;
  btn.textContent = n > 5 ? 'Select up to 5' : `Apply to selected (${n})`;
}

function setBadge(row, cls, text) {
  const badge = row.querySelector('.badge');
  badge.className = `badge ${cls}`;
  badge.textContent = text;
}

$('#batch-btn').addEventListener('click', (e) => withBusy(e.currentTarget, 'Applying…', async () => {
  const jobs = selectedJobs();
  const rows = jobs.map((j) => h('div', { class: 'batch-row' }, h('span', { class: 'badge badge-neutral' }, 'queued'), h('span', {}, `${j.title} — ${j.company_name}`)));
  const box = $('#batch');
  box.replaceChildren(h('span', { class: 'label', style: 'margin-top:.9rem' }, 'Applying one by one'), ...rows);
  box.hidden = false;
  let current = -1;
  try {
    const res = await fetch('/api/apply-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text: $('#resume').value,
        jobs: jobs.map((j) => ({ title: j.title, company_name: j.company_name, description: j.description || j.title, url: j.url || '' })),
        user_id: $('#user-id').value.trim(),
        slack_channel: $('#slack-channel').value.trim(),
        github_username: $('#github').value.trim(),
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(detailText(data.detail, res.status));
    }
    await readStream(res, (ev) => {
      if (ev.type === 'batch') {
        current = ev.index - 1;
        resetPipeline();
        trace(`job ${ev.index}/${ev.total}: ${ev.role} @ ${ev.company}`);
        setBadge(rows[current], 'badge-neutral', 'running…');
      } else if (ev.type === 'result') {
        const r = ev.result;
        batchResults[r.run_id] = r;
        const [cls, text] = OUTCOMES[r.outcome] || ['badge-neutral', r.outcome];
        setBadge(rows[current], cls, text.split(',')[0]);
        rows[current].append(h('button', { class: 'btn btn-ghost btn-sm', type: 'button', style: 'margin-left:auto', onclick: () => renderResult(batchResults[r.run_id]) }, 'View'));
        $$('.app-chip').forEach((c) => { if (!c.className.includes('is-')) c.classList.add('is-skipped'); });
      } else if (ev.type === 'batch_done') {
        ev.summary.forEach((s, i) => { if (s.outcome === 'error') setBadge(rows[i], 'badge-danger', 'error'); });
        const drafted = ev.summary.filter((s) => ['drafted', 'sent'].includes(s.outcome)).length;
        toast(`Done: ${drafted} drafted, ${ev.summary.length - drafted} stopped by a gate or error. Undo any run from the Tracker.`);
      } else {
        handleEvent(ev);
      }
    });
  } catch (err) { showError(err.message); }
}));

// ---------------------------------------------------------------- init
(async function init() {
  const tab = location.hash.slice(1);
  if (['run', 'tracker', 'reliability'].includes(tab)) showTab(tab);
  $('#user-id').value = store.get('userId');
  $('#slack-channel').value = store.get('slackChannel');
  $('#github').value = store.get('github');
  const justConnected = new URLSearchParams(location.search).get('connected');
  if (justConnected) {
    toast(`${CONNECT_APPS[justConnected] || 'App'} connected.`);
    history.replaceState(null, '', '/app');
  }
  try {
    const [, defaults] = await Promise.all([loadStatus(), api('/api/defaults')]);
    if (!$('#resume').value) $('#resume').value = defaults.resume;
    await loadConnections();
    checkGithub();
  } catch (err) { showError(`Could not reach the server: ${err.message}`); }
})();
