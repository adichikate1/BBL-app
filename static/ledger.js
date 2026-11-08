/* Bet ledger: storage + maths. Data never leaves this browser (localStorage). */
(function (root) {
  'use strict';
  const KEY = 'bblw.ledger.v1';
  const DEFAULTS = { baseStake: 100, maxStake: 0, lossLimit: 0, odds: 1.9 };
  const r2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;
  const num = (v, d) => { const x = Number(v); return Number.isFinite(x) ? x : d; };

  function normalize(d) {
    const s = Object.assign({}, DEFAULTS, d && d.settings);
    s.baseStake = Math.max(0, num(s.baseStake, DEFAULTS.baseStake));
    s.maxStake = Math.max(0, num(s.maxStake, 0));
    s.lossLimit = Math.max(0, num(s.lossLimit, 0));
    s.odds = num(s.odds, DEFAULTS.odds) > 1 ? num(s.odds, DEFAULTS.odds) : DEFAULTS.odds;
    const ok = ['pending', 'won', 'lost', 'skipped'];
    const records = ((d && Array.isArray(d.records)) ? d.records : [])
      .filter((r) => r && ok.includes(r.status))
      .map((r) => ({
        id: String(r.id || Math.random().toString(36).slice(2)),
        date: String(r.date || '').slice(0, 10),
        time: /^\d{2}:\d{2}$/.test(String(r.time || '')) ? String(r.time) : '',
        code: String(r.code || '').slice(0, 8),
        prob: r.prob != null && r.prob !== '' && num(r.prob, -1) >= 0 && num(r.prob, -1) <= 1 ? num(r.prob, null) : null,
        match: String(r.match || '').slice(0, 120),
        pick: String(r.pick || '').slice(0, 80),
        note: String(r.note || '').slice(0, 200),
        status: r.status,
        stake: Math.max(0, r2(num(r.stake, 0))),
        amount: Math.max(0, r2(num(r.amount, 0))),
        created: num(r.created, 0),
        updated: num(r.updated, num(r.created, 0)),
      }));
    // tombstones: a deleted id must stay deleted when another device's copy is merged in
    const tomb = new Map();
    ((d && Array.isArray(d.deleted)) ? d.deleted : []).forEach((t) => {
      if (t && t.id != null) tomb.set(String(t.id).slice(0, 32), Math.max(tomb.get(String(t.id).slice(0, 32)) || 0, num(t.at, 0)));
    });
    const deleted = [...tomb].map(([id, at]) => ({ id, at })).sort((a, b) => b.at - a.at).slice(0, 5000);
    return { records, deleted, settings: s };
  }

  const order = (r) => r.date + (r.time || '00:00') + String(r.created).padStart(15, '0') + r.id;
  /** Union of two ledgers (this browser + GitHub). Newest edit of a match wins; deletions win over older edits. */
  function merge(a, b) {
    a = normalize(a); b = normalize(b);
    const tomb = new Map();
    a.deleted.concat(b.deleted).forEach((t) => tomb.set(t.id, Math.max(tomb.get(t.id) || 0, t.at)));
    const best = new Map();
    a.records.concat(b.records).forEach((r) => { const c = best.get(r.id); if (!c || r.updated > c.updated) best.set(r.id, r); });
    const records = [...best.values()].filter((r) => !(tomb.has(r.id) && tomb.get(r.id) >= r.updated)).sort((x, y) => order(x).localeCompare(order(y)));
    const deleted = [...tomb].map(([id, at]) => ({ id, at })).sort((x, y) => y.at - x.at).slice(0, 5000);
    return { records, deleted, settings: a.settings };
  }
  /** Settings-independent fingerprint, to tell whether a merge changed anything. */
  function canon(st) {
    const n = normalize(st);
    return JSON.stringify([n.records.slice().sort((x, y) => order(x).localeCompare(order(y))), n.deleted.slice().sort((x, y) => x.id.localeCompare(y.id))]);
  }

  function load() {
    try { const raw = localStorage.getItem(KEY); return normalize(raw ? JSON.parse(raw) : null); }
    catch (e) { return normalize(null); }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); return true; } catch (e) { return false; }
  }

  /** Signed profit/loss of one record: won -> +profit, lost -> -loss, pending/skipped -> 0. */
  function pnl(r) { return r.status === 'won' ? r.amount : r.status === 'lost' ? -r.amount : 0; }

  function summarize(records, settings) {
    const s = Object.assign({}, DEFAULTS, settings);
    let won = 0, lost = 0, skipped = 0, pending = 0, net = 0, staked = 0, pendingStake = 0;
    for (const r of records) {
      if (r.status === 'won') { won++; net += r.amount; staked += r.stake; }
      else if (r.status === 'lost') { lost++; net -= r.amount; staked += r.stake; }
      else if (r.status === 'skipped') skipped++;
      else { pending++; pendingStake += r.stake; }
    }
    net = r2(net);
    const played = won + lost;

    // Target profit for the next match = Net Loss / (matches won - matches lost). Skipped and pending are not counted.
    //  - not in loss (net >= 0) or nothing played -> base target
    //  - in loss and the result is negative (more lost than won) -> that result, as a positive target
    //  - in loss and the result is positive (more won than lost) -> base target
    //  - in loss but won == lost -> division by zero, so base target ('even')
    const diff = won - lost;
    let raw = s.baseStake, reason = 'base', value = null;
    if (net < 0 && played > 0) {
      if (diff === 0) reason = 'even';
      else {
        value = r2(-net / diff);
        if (value < 0) { raw = -value; reason = 'formula'; }
      }
    }
    const targetAmount = Math.max(0, Math.round(raw));
    // Stake needed to win that profit at the expected odds (the cap applies to the stake, not to the profit).
    let stake = null, uncapped = null, capped = false;
    if (s.odds > 1) {
      uncapped = Math.max(0, Math.round(targetAmount / (s.odds - 1))); stake = uncapped;
      if (s.maxStake > 0 && stake > s.maxStake) { stake = s.maxStake; capped = true; }
    }

    return {
      played, won, lost, skipped, pending, net, staked: r2(staked), pendingStake: r2(pendingStake),
      winRate: played ? won / played : 0,
      roi: staked ? net / staked : 0,
      target: { amount: targetAmount, raw: r2(raw), reason, value, diff },
      stake: { amount: stake, uncapped, capped },
      ifWin: stake == null ? null : r2(net + stake * (s.odds - 1)),
      ifLose: stake == null ? null : r2(net - stake),
      limitHit: s.lossLimit > 0 && net <= -s.lossLimit,
    };
  }

  /** Running net after each settled record, oldest first (for the history table). */
  function withRunning(records) {
    const sorted = records.slice().sort((a, b) => (a.date + (a.time || '00:00') + String(a.created).padStart(15, '0')).localeCompare(b.date + (b.time || '00:00') + String(b.created).padStart(15, '0')));
    let run = 0;
    return sorted.map((r) => { run = r2(run + pnl(r)); return Object.assign({}, r, { pnl: pnl(r), running: run }); });
  }

  const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2, minimumFractionDigits: 0 });
  const money = (n) => inr.format(n);
  const signed = (n) => (n > 0 ? '+' : n < 0 ? '−' : '') + money(Math.abs(n));

  function suggest() { const st = load(); const s = summarize(st.records, st.settings); return Object.assign({ settings: st.settings }, s); }

  function csv(records) {
    const esc = (v) => { let t = String(v ?? ''); if (/^[=+\-@\t\r]/.test(t)) t = "'" + t; return '"' + t.replace(/"/g, '""') + '"'; };
    const rows = [['date', 'time', 'match', 'pick', 'status', 'stake', 'profit_loss', 'note', 'crex_code']];
    withRunning(records).forEach((r) => rows.push([r.date, r.time, r.match, r.pick, r.status, r.stake, r.pnl, r.note, r.code]));
    return rows.map((r) => r.map(esc).join(',')).join('\r\n');
  }

  const api = { KEY, DEFAULTS, normalize, merge, canon, load, save, pnl, summarize, withRunning, money, signed, suggest, csv };
  root.Ledger = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
