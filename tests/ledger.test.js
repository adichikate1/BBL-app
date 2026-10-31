const assert = require('assert');
const L = require('../static/ledger.js');
const rec = (status, stake, amount) => ({ id: Math.random().toString(36), date: '2026-11-01', match: 'A vs B', pick: 'A', status, stake, amount, created: 0 });
let n = 0; const t = (name, fn) => { fn(); n++; console.log('ok -', name); };

t("user's example: 3 matches played, all lost, total -500 -> next stake 500/3 = 167", () => {
  const s = L.summarize([rec('lost', 100, 100), rec('lost', 150, 150), rec('lost', 250, 250)], L.DEFAULTS);
  assert.strictEqual(s.net, -500); assert.strictEqual(s.played, 3);
  assert.strictEqual(s.nextStake.raw, 166.67); assert.strictEqual(s.nextStake.amount, 167);
  assert.strictEqual(s.nextStake.reason, 'recover');
});
t('profit -> base stake, no recovery', () => {
  const s = L.summarize([rec('won', 100, 90), rec('lost', 100, 100), rec('won', 100, 190)], { ...L.DEFAULTS, baseStake: 100 });
  assert.strictEqual(s.net, 180); assert.strictEqual(s.nextStake.amount, 100); assert.strictEqual(s.nextStake.reason, 'base');
});
t('skipped and pending matches are NOT counted in the divisor', () => {
  const s = L.summarize([rec('lost', 100, 100), rec('lost', 200, 200), rec('skipped', 0, 0), rec('pending', 50, 0)], L.DEFAULTS);
  assert.strictEqual(s.played, 2); assert.strictEqual(s.skipped, 1); assert.strictEqual(s.pending, 1);
  assert.strictEqual(s.nextStake.amount, 150); assert.strictEqual(s.pendingStake, 50);
});
t('net uses wins too: loss 700, win 200 over 3 played -> 500/3', () => {
  const s = L.summarize([rec('lost', 350, 350), rec('lost', 350, 350), rec('won', 200, 200)], L.DEFAULTS);
  assert.strictEqual(s.net, -500); assert.strictEqual(s.nextStake.amount, 167);
});
t('no matches yet -> base stake', () => {
  const s = L.summarize([], L.DEFAULTS); assert.strictEqual(s.nextStake.amount, 100); assert.strictEqual(s.net, 0);
});
t('max stake cap', () => {
  const s = L.summarize([rec('lost', 900, 900)], { ...L.DEFAULTS, maxStake: 300 });
  assert.strictEqual(s.nextStake.amount, 300); assert.ok(s.nextStake.capped); assert.strictEqual(s.nextStake.raw, 900);
});
t('loss limit flag', () => {
  const recs = [rec('lost', 300, 300), rec('lost', 300, 300)];
  assert.ok(L.summarize(recs, { ...L.DEFAULTS, lossLimit: 600 }).limitHit);
  assert.ok(!L.summarize(recs, { ...L.DEFAULTS, lossLimit: 601 }).limitHit);
  assert.ok(!L.summarize(recs, { ...L.DEFAULTS, lossLimit: 0 }).limitHit);
});
t('what-if after the suggested bet (odds 1.9): a win does not clear a 500 loss', () => {
  const s = L.summarize([rec('lost', 100, 100), rec('lost', 150, 150), rec('lost', 250, 250)], { ...L.DEFAULTS, odds: 1.9 });
  assert.strictEqual(s.ifWin, -500 + 167 * 0.9); assert.ok(s.ifWin < 0); assert.strictEqual(s.ifLose, -667);
});
t('running net, chronological', () => {
  const a = { ...rec('lost', 100, 100), date: '2026-11-02' }, b = { ...rec('won', 100, 90), date: '2026-11-01' };
  const r = L.withRunning([a, b]); assert.deepStrictEqual(r.map((x) => x.running), [90, -10]);
});
t('normalize drops junk and clamps', () => {
  const st = L.normalize({ records: [{ status: 'hacked' }, null, { status: 'won', amount: -5, stake: 'x' }], settings: { odds: 0.5, baseStake: -3 } });
  assert.strictEqual(st.records.length, 1); assert.strictEqual(st.records[0].amount, 0); assert.strictEqual(st.settings.odds, 1.9); assert.strictEqual(st.settings.baseStake, 0);
});
t('csv escapes quotes and blocks formula injection', () => {
  const out = L.csv([{ ...rec('won', 10, 5), match: '=HYPERLINK("x")', note: 'a,"b"' }]);
  assert.ok(out.includes("\"'=HYPERLINK(\"\"x\"\")\"")); assert.ok(out.includes('"a,""b"""'));
});
t('money format is INR', () => { assert.ok(L.money(1234.5).includes('1,234.5')); assert.ok(L.signed(-500).startsWith('−')); });

t('time/code/prob are kept; same-day matches sort by time; bad time dropped', () => {
  const st = L.normalize({ records: [
    { id: 'b', date: '2026-11-01', time: '14:00', code: 'PZ8', prob: 0.61, match: 'B', status: 'lost', stake: 100, amount: 100, created: 2 },
    { id: 'a', date: '2026-11-01', time: '09:30', code: 'PZ7', match: 'A', status: 'won', stake: 100, amount: 90, created: 5 },
    { id: 'c', date: '2026-11-01', time: '9:5', match: 'C', status: 'skipped', created: 1 }] });
  assert.strictEqual(st.records[0].prob, 0.61); assert.strictEqual(st.records[1].prob, null); assert.strictEqual(st.records[2].time, '');
  assert.deepStrictEqual(L.withRunning(st.records).map((r) => r.id), ['c', 'a', 'b']);
  assert.ok(L.csv(st.records).includes('"09:30","A"'));
});
console.log(n + ' ledger tests passed');
