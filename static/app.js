(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const form = $('form'), t1 = $('team1'), t2 = $('team2'), stats = $('stats');
  const err = $('error'), go = $('go'), reset = $('reset'), result = $('result');
  const short = (n) => n.replace(/ Women$/, '');
  const STEP = { form: 1, h2h: 1, nrr5: 0.01, avgruns: 0.1, avgwk: 0.1 };
  const HINT = { form: '0–5', h2h: '0–5' };
  let features = [], defaults = null;

  const showError = (msg) => { err.textContent = msg || ''; err.hidden = !msg; };

  function buildStatRows() {
    features.forEach((f, i) => {
      const row = document.createElement('div');
      row.className = 'statrow';
      const mk = (side) => {
        const inp = document.createElement('input');
        inp.type = 'number'; inp.inputMode = 'decimal';
        inp.id = `${side}-${f.key}`; inp.name = `${side}-${f.key}`;
        inp.step = STEP[f.key]; inp.required = true;
        if (f.key === 'form' || f.key === 'h2h') { inp.min = 0; inp.max = 5; }
        inp.setAttribute('aria-label', `${f.label} – ${side === 't1' ? 'Team 1' : 'Team 2'}`);
        return inp;
      };
      const lab = document.createElement('div');
      lab.className = 'lab';
      const n = document.createElement('span'); n.className = 'num'; n.textContent = String(i + 1).padStart(2, '0');
      const t = document.createElement('span'); t.textContent = f.label;
      lab.append(n, t);
      if (HINT[f.key]) { const h = document.createElement('em'); h.textContent = HINT[f.key]; lab.append(h); }
      row.append(mk('t1'), lab, mk('t2'));
      stats.append(row);
    });
  }

  const field = (side, key) => $(`${side}-${key}`);

  function fill(d) {
    features.forEach((f) => {
      ['t1', 't2'].forEach((s) => { field(s, f.key).value = d[s][f.key]; field(s, f.key).removeAttribute('aria-invalid'); });
    });
  }

  function headers() {
    $('h1').textContent = t1.value ? short(t1.value) : 'Team 1';
    $('h2').textContent = t2.value ? short(t2.value) : 'Team 2';
  }

  async function loadDefaults() {
    headers();
    showError('');
    if (!t1.value || !t2.value || t1.value === t2.value) {
      reset.disabled = true; defaults = null;
      if (t1.value && t1.value === t2.value) showError('Pick two different teams.');
      return;
    }
    try {
      const r = await fetch(`/api/defaults?team1=${encodeURIComponent(t1.value)}&team2=${encodeURIComponent(t2.value)}`);
      if (!r.ok) throw new Error((await r.json()).error || 'Could not load stats.');
      defaults = await r.json(); fill(defaults); reset.disabled = false;
    } catch (e) { showError(e.message); }
  }

  function collect() {
    const body = { team1: t1.value, team2: t2.value, t1: {}, t2: {} };
    let ok = true;
    features.forEach((f) => ['t1', 't2'].forEach((s) => {
      const el = field(s, f.key), v = el.value.trim();
      const bad = v === '' || !Number.isFinite(Number(v)) || (el.min !== '' && Number(v) < Number(el.min)) || (el.max !== '' && Number(v) > Number(el.max));
      if (bad) { ok = false; el.setAttribute('aria-invalid', 'true'); } else { el.removeAttribute('aria-invalid'); }
      body[s][f.key] = v === '' ? null : Number(v);
    }));
    return ok ? body : null;
  }

  const pct = (p) => `${(p * 100).toFixed(1)}%`;

  function render(r) {
    $('winner').textContent = short(r.winner);
    $('strength').textContent = r.strength;
    $('n1').textContent = short(r.team1); $('n2').textContent = short(r.team2);
    $('p1').textContent = pct(r.p_team1); $('p2').textContent = pct(r.p_team2);
    $('bar1').style.width = '50%';
    const list = $('factors'); list.replaceChildren();
    const max = Math.max(0.4, ...r.factors.map((f) => Math.abs(f.effect)));
    r.factors.forEach((f) => {
      const li = document.createElement('li');
      const l = document.createElement('div'); l.className = 'fl';
      l.textContent = f.label;
      const sm = document.createElement('small');
      sm.textContent = f.effect === 0 ? 'no effect' : `favours ${short(f.effect > 0 ? r.team1 : r.team2)}`;
      l.append(sm);
      const bar = document.createElement('div'); bar.className = 'fbar';
      const i = document.createElement('i'); i.className = f.effect >= 0 ? 't1' : 't2'; i.style.width = '0%';
      bar.append(i); li.append(l, bar); list.append(li);
      requestAnimationFrame(() => requestAnimationFrame(() => { i.style.width = `${Math.min(50, (Math.abs(f.effect) / max) * 50)}%`; }));
    });
    showStake(r);
    result.hidden = false;
    requestAnimationFrame(() => { $('bar1').style.width = `${r.p_team1 * 100}%`; });
    result.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }

  function showStake(r) {
    const box = $('stakebox');
    if (!window.Ledger) { box.hidden = true; return; }
    const s = window.Ledger.suggest(), n = s.nextStake, m = window.Ledger.money;
    let t = n.reason === 'recover'
      ? `Next stake: ${m(n.amount)} (net ${window.Ledger.signed(s.net)} over ${s.played} played match${s.played === 1 ? '' : 'es'}).`
      : `Next stake: ${m(n.amount)} (base stake, no loss to recover).`;
    if (s.limitHit) t = `Your stop-loss is reached: do not bet. ${t}`;
    else if (r.strength === 'Toss-up') t += ' The model sees this as a toss-up (under 5% edge), so skipping is also an option.';
    $('stake-line').textContent = t;
    $('stake-link').href = `/tracker?match=${encodeURIComponent(short(r.team1) + ' vs ' + short(r.team2))}&pick=${encodeURIComponent(short(r.winner))}`;
    box.hidden = false;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault(); showError('');
    if (!t1.value || !t2.value) return showError('Please select both teams.');
    if (t1.value === t2.value) return showError('Pick two different teams.');
    const body = collect();
    if (!body) return showError('Please fill every field with a valid number (form and head-to-head are 0–5).');
    go.disabled = true; go.firstElementChild.textContent = 'Predicting…';
    try {
      const r = await fetch('/api/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Prediction failed.');
      render(data);
    } catch (ex) { showError(ex.message || 'Network error. Please try again.'); }
    finally { go.disabled = false; go.firstElementChild.textContent = 'Predict winner'; }
  });

  // --- auto-fetch everything from a CREX match code ---
  const code = $('code'), fetchBtn = $('fetch'), note = $('fetchnote');
  async function fetchByCode() {
    showError(''); note.hidden = true;
    const c = code.value.trim();
    if (!/^[A-Za-z0-9]{2,8}$/.test(c)) return showError('Enter the CREX match code (letters/numbers only, e.g. PZ7).');
    fetchBtn.disabled = true; fetchBtn.textContent = 'Fetching…';
    try {
      const r = await fetch(`/api/fetch?code=${encodeURIComponent(c)}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Could not fetch this match.');
      t1.value = d.team1; t2.value = d.team2; headers();
      defaults = { t1: d.t1, t2: d.t2 }; fill(defaults); reset.disabled = false;
      const u = d.matches_used, few = u.t1 < 5 || u.t2 < 5;
      note.textContent = `Loaded from CREX: ${short(d.team1)} (${u.t1} past matches) vs ${short(d.team2)} (${u.t2})` +
        (few ? ' — fewer than 5 available, so averaged over those.' : '. You can still edit any number and predict again.');
      note.hidden = false;
      form.requestSubmit();
    } catch (ex) { showError(ex.message || 'Network error. Please try again.'); }
    finally { fetchBtn.disabled = false; fetchBtn.textContent = 'Fetch & predict'; }
  }
  fetchBtn.addEventListener('click', fetchByCode);
  code.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); fetchByCode(); } });

  stats.addEventListener('input', (e) => { e.target.removeAttribute('aria-invalid'); showError(''); });
  [t1, t2].forEach((s) => s.addEventListener('change', loadDefaults));
  reset.addEventListener('click', () => defaults && fill(defaults));

  // custom cursor (fine pointers only)
  const cur = document.querySelector('.cursor');
  if (cur && matchMedia('(hover:hover) and (pointer:fine)').matches) {
    addEventListener('pointermove', (e) => { cur.classList.add('on'); cur.style.left = `${e.clientX}px`; cur.style.top = `${e.clientY}px`; }, { passive: true });
    document.addEventListener('pointerover', (e) => cur.classList.toggle('big', !!e.target.closest('button,select,a')));
  }

  (async function init() {
    try {
      const r = await fetch('/api/teams'); const d = await r.json();
      features = d.features;
      $('acc-overall').textContent = `${(d.validation.overall * 100).toFixed(0)}%`;
      [t1, t2].forEach((s, idx) => {
        const ph = document.createElement('option'); ph.value = ''; ph.textContent = idx ? 'Select Team 2' : 'Select Team 1'; ph.disabled = true; ph.selected = true;
        s.append(ph);
        d.teams.forEach((t) => { const o = document.createElement('option'); o.value = t; o.textContent = short(t); s.append(o); });
      });
      buildStatRows();
    } catch { showError('Could not load the model. Please refresh.'); go.disabled = true; }
  })();
})();
