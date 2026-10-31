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
      }));
    return { records, settings: s };
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

    // Next stake: in loss -> (total loss) / (matches actually played); otherwise the base stake.
    // Skipped and still-pending matches are not part of "played".
    let raw, reason;
    if (net < 0 && played > 0) { raw = -net / played; reason = 'recover'; }
    else { raw = s.baseStake; reason = 'base'; }
    let amount = Math.max(0, Math.round(raw));
    let capped = false;
    if (s.maxStake > 0 && amount > s.maxStake) { amount = s.maxStake; capped = true; }

    return {
      played, won, lost, skipped, pending, net, staked: r2(staked), pendingStake: r2(pendingStake),
      winRate: played ? won / played : 0,
      roi: staked ? net / staked : 0,
      nextStake: { amount, raw: r2(raw), reason, capped },
      ifWin: r2(net + amount * (s.odds - 1)),
      ifLose: r2(net - amount),
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

  const api = { KEY, DEFAULTS, normalize, load, save, pnl, summarize, withRunning, money, signed, suggest, csv };
  root.Ledger = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
