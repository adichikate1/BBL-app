(() => {
  'use strict';
  const L = window.Ledger;
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  let state = L.load();
  let editingId = null;
  let modelPick = '', modelProb = null;   // last CREX fetch: the model's pick and its probability
  let lastDate = '';
  const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
  const pct = (x) => `${(x * 100).toFixed(0)}%`;

  function persist(emptyOk) { $('storewarn').hidden = L.save(state); scheduleSync(emptyOk); }

  // ---------- summary + next stake ----------
  function renderSummary() {
    const s = L.summarize(state.records, state.settings);
    const tiles = $('tiles'); tiles.replaceChildren();
    const tile = (label, value, sub, cls) => {
      const t = el('div', 'tile' + (cls ? ' ' + cls : ''));
      t.append(el('span', 'tl', label), el('strong', null, value), el('em', null, sub || ''));
      tiles.append(t);
    };
    tile('Net profit / loss', L.signed(s.net), s.played ? `ROI ${(s.roi * 100).toFixed(0)}% on ${L.money(s.staked)} staked` : 'nothing settled yet', s.net > 0 ? 'good' : s.net < 0 ? 'bad' : '');
    tile('Matches played', String(s.played), `${s.won} won · ${s.lost} lost${s.played ? ' · ' + pct(s.winRate) + ' win rate' : ''}`);
    tile('Skipped', String(s.skipped), 'no bet placed');
    tile('Pending', String(s.pending), s.pending ? `${L.money(s.pendingStake)} at risk` : 'none open');

    const n = s.nextStake;
    $('nb-amount').textContent = L.money(n.amount);
    let why;
    if (n.reason === 'recover') {
      why = `You are ${L.signed(s.net)} over ${s.played} played match${s.played === 1 ? '' : 'es'}: ${L.money(-s.net)} ÷ ${s.played} = ${L.money(n.raw)}` + (n.amount !== n.raw && !n.capped ? `, rounded to ${L.money(n.amount)}.` : '.');
    } else {
      why = s.net > 0 ? `You are in profit (${L.signed(s.net)}), so no recovery is needed: your base stake.` : 'No loss to recover: your base stake.';
    }
    if (n.capped) why += ` Capped at your max stake of ${L.money(state.settings.maxStake)} (uncapped: ${L.money(n.raw)}).`;
    $('nb-why').textContent = why;
    $('nb-whatif').textContent = `If this bet wins at odds ${state.settings.odds}: net ${L.signed(s.ifWin)}.  If it loses: net ${L.signed(s.ifLose)}.`;

    const lim = $('limit');
    lim.hidden = !s.limitHit;
    if (s.limitHit) lim.textContent = `Stop-loss reached: your net loss ${L.money(-s.net)} is at or above your limit of ${L.money(state.settings.lossLimit)}. Stop betting now.`;
    return s;
  }

  // ---------- history ----------
  function renderHistory() {
    const rows = L.withRunning(state.records);
    const body = document.querySelector('#hist tbody'); body.replaceChildren();
    $('empty').hidden = rows.length > 0;
    $('hist').hidden = rows.length === 0;
    rows.forEach((r, i) => {
      const tr = el('tr', 'st-' + r.status);
      const settled = r.status === 'won' || r.status === 'lost';
      const when = el('td', null, r.date); if (r.time) when.append(el('small', null, r.time));
      const pk = el('td', null, r.pick || '—'); if (r.pick && r.prob != null) pk.append(el('small', null, `model ${pct(r.prob)}`));
      tr.append(el('td', null, String(i + 1)), when, el('td', 'm', r.match), pk);
      const st = el('td'); st.append(el('span', 'badge ' + r.status, r.status)); tr.append(st);
      tr.append(el('td', 'r', r.status === 'skipped' ? '—' : L.money(r.stake)));
      const p = el('td', 'r' + (r.pnl > 0 ? ' good' : r.pnl < 0 ? ' bad' : ''), settled ? L.signed(r.pnl) : '—');
      tr.append(p, el('td', 'r', settled ? L.signed(r.running) : '—'));
      const act = el('td', 'r');
      const ed = el('button', 'link', 'Edit'); ed.type = 'button'; ed.addEventListener('click', () => startEdit(r.id));
      const del = el('button', 'link danger', 'Delete'); del.type = 'button';
      del.addEventListener('click', () => { if (confirm('Delete this match from your log?')) { state.records = state.records.filter((x) => x.id !== r.id); if (editingId === r.id) resetForm(); persist(state.records.length === 0); renderAll(); } });
      act.append(ed, document.createTextNode(' '), del); tr.append(act);
      body.append(tr);
    });
  }

  // ---------- form ----------
  function syncStatus() {
    const st = $('f-status').value;
    $('f-stake').disabled = st === 'skipped';
    $('f-amount').disabled = st === 'pending' || st === 'skipped';
    $('amount-text').textContent = st === 'won' ? 'Profit won (₹)' : st === 'lost' ? 'Loss (₹)' : 'Amount (₹)';
    $('f-amount').placeholder = st === 'won' ? 'net profit' : st === 'lost' ? 'default = stake' : '';
    if (st === 'pending' || st === 'skipped') $('f-amount').value = '';
    if (st === 'skipped') $('f-stake').value = '';
  }
  function setPick(pick, prob) { $('f-pick').value = pick || ''; $('pickprob').textContent = pick && prob != null ? `model: ${pct(prob)}` : ''; }
  function resetForm(prefill, keepDate) {
    editingId = null; modelPick = ''; modelProb = null;
    $('entry').reset();
    $('f-date').value = keepDate && lastDate ? lastDate : today();
    const s = L.summarize(state.records, state.settings);
    $('f-stake').value = s.nextStake.amount;
    $('f-status').value = 'pending';
    setPick('', null);
    if (prefill) { $('f-match').value = prefill.match || ''; $('f-pick').value = prefill.pick || ''; }
    $('fetchnote').hidden = true;
    $('entry-title').firstChild.textContent = 'Log a match ';
    $('save-label').textContent = 'Add match';
    $('cancel-edit').hidden = true;
    $('entry-error').hidden = true;
    syncStatus();
  }
  function startEdit(id) {
    const r = state.records.find((x) => x.id === id); if (!r) return;
    editingId = id;
    $('f-date').value = r.date; $('f-time').value = r.time || ''; $('f-code').value = r.code || ''; $('f-match').value = r.match; $('f-note').value = r.note;
    modelPick = r.prob != null ? r.pick : ''; modelProb = r.prob; setPick(r.pick, r.prob);
    $('f-status').value = r.status; syncStatus();
    $('f-stake').value = r.status === 'skipped' ? '' : r.stake;
    $('f-amount').value = (r.status === 'won' || r.status === 'lost') ? r.amount : '';
    $('entry-title').firstChild.textContent = 'Editing a match ';
    $('save-label').textContent = 'Update match';
    $('cancel-edit').hidden = false;
    $('entry').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  function fail(msg) { const e = $('entry-error'); e.textContent = msg; e.hidden = false; }

  // Never copy the stake into the amount here: the stake may still change. A "lost" row with an empty
  // amount is saved as a loss equal to the stake (see submit handler).
  $('f-status').addEventListener('change', () => { $('f-amount').value = ''; syncStatus(); });
  $('cancel-edit').addEventListener('click', () => resetForm());
  $('entry').addEventListener('submit', (e) => {
    e.preventDefault();
    const status = $('f-status').value, match = $('f-match').value.trim();
    const stake = Number($('f-stake').value || 0), amtRaw = $('f-amount').value;
    if (!$('f-date').value) return fail('Pick a date.');
    if (!match) return fail('Enter the match (e.g. Brisbane Heat vs Sydney Sixers).');
    if (status !== 'skipped' && !(stake > 0)) return fail('Enter the stake (more than 0).');
    let amount = 0;
    if (status === 'won') { amount = Number(amtRaw); if (!(amount > 0)) return fail('Enter the profit you won (more than 0).'); }
    if (status === 'lost') { amount = amtRaw === '' ? stake : Number(amtRaw); if (!(amount > 0)) return fail('Enter the loss amount (more than 0).'); }
    const code = $('f-code').value.trim().toUpperCase(), pick = $('f-pick').value.trim();
    if (code && state.records.some((x) => x.code === code && x.id !== editingId)) return fail(`Match ${code} is already in your log. Edit that row instead.`);
    const rec = { id: editingId || Date.now().toString(36) + Math.random().toString(36).slice(2, 6), date: $('f-date').value, time: $('f-time').value, code, match, pick,
      prob: pick && pick === modelPick ? modelProb : null,
      note: $('f-note').value.trim(), status, stake: status === 'skipped' ? 0 : stake, amount,
      created: editingId ? (state.records.find((x) => x.id === editingId) || {}).created || Date.now() : Date.now() };
    state.records = editingId ? state.records.map((x) => (x.id === editingId ? rec : x)) : state.records.concat(rec);
    state = L.normalize(state);
    lastDate = rec.date;
    persist(); resetForm(null, true); renderAll();
  });

  // ---------- settings / export / clear ----------
  function loadSettings() {
    const s = state.settings;
    $('s-base').value = s.baseStake; $('s-max').value = s.maxStake || ''; $('s-limit').value = s.lossLimit || ''; $('s-odds').value = s.odds;
  }
  ['s-base', 's-max', 's-limit', 's-odds'].forEach((id) => $(id).addEventListener('change', () => {
    state.settings = { baseStake: $('s-base').value, maxStake: $('s-max').value || 0, lossLimit: $('s-limit').value || 0, odds: $('s-odds').value };
    state = L.normalize(state); loadSettings(); persist(); renderAll(); if (!editingId) $('f-stake').value = L.summarize(state.records, state.settings).nextStake.amount;
  }));
  $('export').addEventListener('click', () => {
    const blob = new Blob([L.csv(state.records)], { type: 'text/csv;charset=utf-8' });
    const a = el('a'); a.href = URL.createObjectURL(blob); a.download = `bet-log-${today()}.csv`; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $('clear').addEventListener('click', () => {
    if (!state.records.length) return;
    if (confirm('Delete ALL logged matches? This cannot be undone (export a CSV first if you want a copy).' + (sync.key ? ' The GitHub copy will be emptied too (older commits stay in its history).' : ''))) { state.records = []; persist(true); resetForm(); renderAll(); }
  });

  // ---------- auto-fill from a CREX match code ----------
  async function fetchMatch() {
    const note = $('fetchnote'), btn = $('f-fetch'), c = $('f-code').value.trim();
    note.hidden = true;
    const say = (t, bad) => { note.textContent = t; note.classList.toggle('bad', !!bad); note.hidden = false; };
    if (!/^[A-Za-z0-9]{2,8}$/.test(c)) return say('Enter the CREX match code (letters/numbers only, e.g. PZ7).', true);
    if (!editingId && state.records.some((x) => x.code === c.toUpperCase())) return say(`Match ${c.toUpperCase()} is already in your log.`, true);
    btn.disabled = true; btn.textContent = 'Fetching…';
    try {
      const r = await fetch(`/api/fetch?code=${encodeURIComponent(c)}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Could not fetch this match.');
      $('f-code').value = d.code.toUpperCase();
      $('f-match').value = `${d.team1} vs ${d.team2}`;
      if (d.date) $('f-date').value = d.date;
      if (d.time) $('f-time').value = d.time;
      const p = d.prediction;
      if (p) { modelPick = p.winner; modelProb = p.winner === d.team1 ? p.p_team1 : p.p_team2; setPick(modelPick, modelProb); }
      else { modelPick = ''; modelProb = null; setPick('', null); }
      say(`Loaded: ${d.team1} vs ${d.team2}` + (d.date ? ` · ${d.date}${d.time ? ' ' + d.time : ''}` : ' · date not found on CREX, check it') +
          (p ? ` · model picks ${p.winner} (${pct(modelProb)}, ${p.strength.toLowerCase()})` : ' · no model pick (stats out of range)') + '. Now set status, stake and note.');
    } catch (ex) { say(ex.message || 'Network error. Please try again.', true); }
    finally { btn.disabled = false; btn.textContent = 'Fetch match'; }
  }
  $('f-fetch').addEventListener('click', fetchMatch);
  $('f-code').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); fetchMatch(); } });
  $('f-pick').addEventListener('input', () => { if ($('f-pick').value.trim() !== modelPick) $('pickprob').textContent = ''; else if (modelPick) $('pickprob').textContent = `model: ${pct(modelProb)}`; });

  // ---------- GitHub backup (server holds the token; the browser only holds the sync key) ----------
  const sync = { key: '', enabled: false, busy: false, dirty: false, timer: null, emptyOk: false };
  const KEYSTORE = 'bblw.synckey';
  const syncMsg = (t, bad) => { $('sync-msg').textContent = t; $('sync-msg').classList.toggle('bad', !!bad); };
  const syncState = (t) => { $('sync-state').textContent = t; };
  const hhmm = () => new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  function syncUi() {
    const on = !!sync.key;
    $('sync-now').disabled = !on; $('sync-load').disabled = !on; $('sync-off').hidden = !on;
    $('sync-key').hidden = on; $('sync-connect').hidden = on;
    if (!on) syncState('not connected');
  }
  async function api(path, opt) {
    const r = await fetch(path, Object.assign({ headers: { 'X-Sync-Key': sync.key, 'Content-Type': 'application/json' } }, opt));
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `Server error (${r.status}).`);
    return d;
  }
  function scheduleSync(emptyOk) {
    if (!sync.key) return;
    sync.emptyOk = sync.emptyOk || !!emptyOk;
    clearTimeout(sync.timer); syncState('pending…');
    sync.timer = setTimeout(syncNow, 1200);
  }
  async function syncNow() {
    if (!sync.key) return;
    if (sync.busy) { sync.dirty = true; return; }
    sync.busy = true; syncState('saving…');
    const allowEmpty = sync.emptyOk; sync.emptyOk = false;
    try {
      const d = await api('/api/sync/save', { method: 'POST', body: JSON.stringify({ records: state.records, settings: state.settings, allow_empty: allowEmpty }) });
      syncState(`saved ${hhmm()}`);
      syncMsg(d.unchanged ? `GitHub already up to date (${d.count} matches).` : `Saved ${d.count} matches to ${d.path} (commit ${d.commit}).`);
    } catch (ex) { syncState('error'); syncMsg(`${ex.message} Your data is safe in this browser; it will retry on the next change or “Sync now”.`, true); }
    finally { sync.busy = false; if (sync.dirty) { sync.dirty = false; syncNow(); } }
  }
  async function loadRemote(confirmReplace) {
    syncState('loading…');
    try {
      const d = await api('/api/sync/load');
      if (!d.ledger) { syncState('empty'); syncMsg('Nothing saved in GitHub yet.'); return false; }
      const n = d.ledger.records.length;
      if (confirmReplace && !confirm(`Replace the ${state.records.length} matches in this browser with the ${n} matches from GitHub?`)) { syncState(`saved ${hhmm()}`); return false; }
      state = L.normalize(d.ledger); $('storewarn').hidden = L.save(state);
      loadSettings(); resetForm(); renderAll();
      syncState(`loaded ${hhmm()}`); syncMsg(`Loaded ${n} matches from GitHub.`);
      return true;
    } catch (ex) { syncState('error'); syncMsg(ex.message, true); return false; }
  }
  $('sync-connect').addEventListener('click', async () => {
    const k = $('sync-key').value.trim(); if (!k) return syncMsg('Enter the sync key.', true);
    sync.key = k; syncMsg('Checking…');
    try {
      const d = await api('/api/sync/load');
      try { localStorage.setItem(KEYSTORE, k); } catch (e) { /* key just won't be remembered */ }
      $('sync-key').value = ''; syncUi();
      if (!d.ledger) { syncMsg('Connected. GitHub has no ledger yet.'); if (state.records.length) syncNow(); else syncState('connected'); }
      else if (!state.records.length) await loadRemote(false);
      else { syncState('connected'); syncMsg(`Connected. GitHub has ${d.ledger.records.length} matches and this browser has ${state.records.length}. Nothing was changed: use “Load from GitHub” to take GitHub's copy, or “Sync now” to overwrite GitHub with this browser's.`); }
    } catch (ex) { sync.key = ''; syncUi(); syncMsg(ex.message, true); }
  });
  $('sync-now').addEventListener('click', () => {
    if (!state.records.length) { if (!confirm('This browser has no matches. Empty the GitHub ledger too?')) return; sync.emptyOk = true; }
    syncNow();
  });
  $('sync-load').addEventListener('click', () => loadRemote(true));
  $('sync-off').addEventListener('click', () => { sync.key = ''; try { localStorage.removeItem(KEYSTORE); } catch (e) { /* ignore */ } syncUi(); syncMsg('Disconnected. Your GitHub file is untouched.'); });
  (async function initSync() {
    try {
      const d = await (await fetch('/api/sync/status')).json();
      if (!d.enabled) return;
      sync.enabled = true; $('syncbox').hidden = false;
      try { sync.key = localStorage.getItem(KEYSTORE) || ''; } catch (e) { sync.key = ''; }
      syncUi();
      if (sync.key) syncState('connected');
    } catch (e) { /* offline: tracker still works locally */ }
  })();

  function renderAll() { renderSummary(); renderHistory(); }

  // custom cursor (fine pointers only)
  const cur = document.querySelector('.cursor');
  if (cur && matchMedia('(hover:hover) and (pointer:fine)').matches) {
    addEventListener('pointermove', (e) => { cur.classList.add('on'); cur.style.left = `${e.clientX}px`; cur.style.top = `${e.clientY}px`; }, { passive: true });
    document.addEventListener('pointerover', (e) => cur.classList.toggle('big', !!e.target.closest('button,select,a,summary')));
  }

  loadSettings();
  const q = new URLSearchParams(location.search);
  resetForm({ match: q.get('match'), pick: q.get('pick') });
  renderAll();
  try { localStorage.setItem('bblw.probe', '1'); localStorage.removeItem('bblw.probe'); } catch (e) { $('storewarn').hidden = false; }
})();
